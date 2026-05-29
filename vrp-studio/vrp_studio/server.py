import argparse
import asyncio
import os
import queue
import threading
import json
import time
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi import UploadFile, File, Form
import uvicorn
from vrp_cli import Problem, Config, RoutingMatrix, solve as vrp_solve

app = FastAPI()

cors_origins = [origin.strip() for origin in os.getenv("VRP_STUDIO_CORS_ORIGINS", "*").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def find_problems():
    problems = []
    base_dirs = [
        Path("data"),
        Path("examples/data"),
        Path("../data"),
        Path("../examples/data")
    ]
    for base_dir in base_dirs:
        if base_dir.exists():
            for path in base_dir.rglob("*.problem.json"):
                problem_path = str(path)
                matrix_path = problem_path.replace(".problem.json", ".matrix.json")
                has_matrix = os.path.exists(matrix_path)

                source = "examples" if "examples" in str(path) else "user"
                problems.append({
                    "id": problem_path,
                    "name": path.stem,
                    "path": problem_path,
                    "matrix_path": matrix_path if has_matrix else None,
                    "source": source
                })
    return problems

@app.get("/api/problems")
async def get_problems():
    return JSONResponse({"problems": find_problems()})

@app.post("/api/upload")
async def upload_problem(file: UploadFile = File(...)):
    try:
        content = await file.read()
        content_str = content.decode("utf-8")

        # Determine if it's solomon (starts with some text usually)
        from vrp_studio.solomon import parse_solomon
        name, problem, matrix = parse_solomon(content_str)

        data_dir = Path("../data") if os.path.exists("../data") else Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)

        # To avoid collisions
        base_name = name.lower().replace(" ", "_")
        if not base_name:
            base_name = file.filename.split('.')[0]

        prob_path = data_dir / f"{base_name}.problem.json"
        matrix_path = data_dir / f"{base_name}.matrix.json"

        with open(prob_path, "w") as f:
            json.dump(problem, f, indent=2)
        with open(matrix_path, "w") as f:
            json.dump(matrix, f, indent=2)

        return JSONResponse({"success": True, "message": "Uploaded and converted successfully", "problem_path": str(prob_path)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

from pydantic import BaseModel

class ProblemRequest(BaseModel):
    problem_path: str

@app.post("/api/problem/initial_state")
async def get_initial_state(req: ProblemRequest):
    try:
        from vrp_cli import Problem
        problem = Problem.from_json(req.problem_path)
        d = problem.to_dict()

        from vrp_cli.vis.tracker import _extract_jobs_meta
        jobs_meta = _extract_jobs_meta(problem)

        # Extract every individual place from every job's pickups, deliveries, services, replacements
        unassigned = []
        for job in d.get("plan", {}).get("jobs", []):
            job_id = job.get("id", "unknown")
            for act_type in ("pickups", "deliveries", "services", "replacements"):
                for act in job.get(act_type, []):
                    for place in act.get("places", []):
                        loc = place.get("location")
                        if loc:
                            tag = place.get("tag", "")
                            label = f"{job_id}{'/' + tag if tag else ''}"
                            unassigned.append({
                                "jobId": label,
                                "location": loc,
                                "actType": {"pickups": "pickup", "deliveries": "delivery", "services": "service", "replacements": "replacement"}.get(act_type, act_type)
                            })

        tours = []
        for vehicle in d.get("fleet", {}).get("vehicles", []):
            vehicle_ids = vehicle.get("vehicleIds", ["v"])
            for vid in vehicle_ids:
                for shift in vehicle.get("shifts", []):
                    stops = []
                    start_loc = shift.get("start", {}).get("location")
                    if start_loc:
                        stops.append({
                            "location": start_loc,
                            "activities": [{"type": "depot"}]
                        })

                    # Extract breaks with a fixed location
                    for brk in shift.get("breaks", []):
                        for place in brk.get("places", []):
                            loc = place.get("location")
                            if loc:
                                stops.append({
                                    "location": loc,
                                    "activities": [{"type": "break"}]
                                })

                    # Extract recharge stations
                    for station in shift.get("recharges", {}).get("stations", []):
                        loc = station.get("location")
                        if loc:
                            stops.append({
                                "location": loc,
                                "activities": [{"type": "recharge"}]
                            })

                    # Extract reload points
                    for reload in shift.get("reloadPoints", []):
                        loc = reload.get("location")
                        if loc:
                            stops.append({
                                "location": loc,
                                "activities": [{"type": "service"}]
                            })

                    if stops:
                        tours.append({"vehicleId": vid, "stops": stops})

        return JSONResponse({
            "jobs_meta": jobs_meta,
            "initial_state": {
                "tours": tours,
                "unassigned": unassigned
            }
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

class SolverThread(threading.Thread):
    def __init__(self, problem_path, matrix_path, max_time, max_gen, parallelism, termination_cfg, heuristic_mode, updates_queue):
        super().__init__()
        self.problem_path = problem_path
        self.matrix_path = matrix_path
        self.max_time = max_time
        self.max_gen = max_gen
        self.parallelism = parallelism
        self.termination_cfg = termination_cfg
        self.heuristic_mode = heuristic_mode
        self.updates_queue = updates_queue
        self._stop_event = threading.Event()
        self.error = None

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            from vrp_cli.vis.tracker import _extract_jobs_meta
            problem = Problem.from_json(self.problem_path)
            matrices = [RoutingMatrix.from_json(self.matrix_path)] if self.matrix_path else None
            preset_dict = {}
            if self.heuristic_mode == "fast":
                preset_dict = {
                    "evolution": {
                        "population": {
                            "type": "elitism",
                            "maxSize": 8,
                            "selectionSize": 4
                        }
                    }
                }
            elif self.heuristic_mode == "deep":
                preset_dict = {
                    "evolution": {
                        "population": {
                            "type": "rosomaxa",
                            "maxEliteSize": 4,
                            "maxNodeSize": 4,
                            "explorationRatio": 0.9
                        }
                    }
                }
            elif self.heuristic_mode == "large_scale":
                preset_dict = {
                    "evolution": {
                        "population": {
                            "type": "rosomaxa",
                            "maxNodeSize": 2,
                            "explorationRatio": 0.4
                        }
                    },
                    "hyper": {
                        "type": "static-selective"
                    }
                }

            config = Config(data=preset_dict)

            # Apply overrides on top of the preset
            config.set_termination(max_time=self.max_time, max_generations=self.max_gen, variation=self.termination_cfg.get("variation") if self.termination_cfg else None)
            if self.parallelism is not None:
                config.set_parallelism(self.parallelism)

            jobs_meta = _extract_jobs_meta(problem)
            self.updates_queue.put({"type": "metadata", "data": jobs_meta})

            start_time = time.time()
            best_cost = float('inf')
            latest_generation = 0

            def build_snapshot(state, solution, is_final=False):
                stats = solution.statistic
                times = stats.get("times", {})

                return {
                    "generation": state,
                    "cost": solution.total_cost,
                    "elapsed_seconds": time.time() - start_time,
                    "tours": solution.tours,
                    "unassigned": solution.unassigned,
                    "final": is_final,
                    "statistic": {
                        "distance": stats.get("distance", 0),
                        "duration": stats.get("duration", 0),
                        "times": {
                            "driving": times.get("driving", 0),
                            "serving": times.get("serving", 0),
                            "waiting": times.get("waiting", 0),
                            "break": times.get("break", 0),
                        }
                    }
                }

            def on_iteration(state, solution):
                nonlocal best_cost, latest_generation
                latest_generation = state
                if self._stop_event.is_set():
                    # We can't cleanly abort vrp_solve yet without killing process, but we stop queueing.
                    return

                current_cost = solution.total_cost
                if current_cost >= best_cost:
                    return
                best_cost = current_cost
                self.updates_queue.put({"type": "iteration", "data": build_snapshot(state, solution)})

            final_solution = vrp_solve(
                problem,
                matrices=matrices,
                config=config,
                on_iteration=on_iteration,
                every=10
            )

            if not self._stop_event.is_set():
                self.updates_queue.put({"type": "iteration", "data": build_snapshot(latest_generation, final_solution, is_final=True)})
            self.updates_queue.put({"type": "finished"})

        except Exception as e:
            self.error = str(e)
            self.updates_queue.put({"type": "error", "message": self.error})

@app.websocket("/ws/solve")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    solver_thread = None
    try:
        data = await websocket.receive_json()
        if data.get("action") == "start":
            problem_path = data.get("problem_path")
            matrix_path = data.get("matrix_path")
            max_time = data.get("max_time", 60)
            max_gen = data.get("max_gen", 3000)
            parallelism = data.get("parallelism")
            heuristic_mode = data.get("heuristic_mode", "default")

            termination_cfg = None
            if data.get("variation_sample") is not None and data.get("variation_cv") is not None:
                termination_cfg = {
                    "variation": {
                        "intervalType": "sample",
                        "value": data.get("variation_sample"),
                        "cv": data.get("variation_cv"),
                        "isGlobal": True
                    }
                }

            updates_queue = queue.Queue()
            solver_thread = SolverThread(problem_path, matrix_path, max_time, max_gen, parallelism, termination_cfg, heuristic_mode, updates_queue)
            solver_thread.start()

            start_time = time.time()
            last_time_sent = 0
            while solver_thread.is_alive() or not updates_queue.empty():
                current_time = time.time()
                elapsed = current_time - start_time
                try:
                    update = updates_queue.get_nowait()
                    if "data" in update and isinstance(update["data"], dict):
                        update["data"]["elapsed_seconds"] = elapsed
                    await websocket.send_json(update)
                    if update["type"] in ["finished", "error"]:
                        break
                except queue.Empty:
                    if current_time - last_time_sent > 0.5:
                        await websocket.send_json({"type": "time", "data": {"elapsed_seconds": elapsed}})
                        last_time_sent = current_time
                    await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        if solver_thread:
            solver_thread.stop()
# Mount frontend if it exists
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")

def main():
    parser = argparse.ArgumentParser(description="VRP Studio Server")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")
    args = parser.parse_args()

    uvicorn.run("vrp_studio.server:app", host="0.0.0.0", port=args.port, reload=True)

if __name__ == "__main__":
    main()
