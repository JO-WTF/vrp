import argparse
import asyncio
import os
import queue
import threading
import json
import time
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import uvicorn
from vrp_cli import Problem, Config, RoutingMatrix, solve as vrp_solve

app = FastAPI()


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
                
                problems.append({
                    "id": problem_path,
                    "name": path.stem,
                    "path": problem_path,
                    "matrix_path": matrix_path if has_matrix else None
                })
    return problems

@app.get("/api/problems")
async def get_problems():
    return JSONResponse({"problems": find_problems()})

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

        unassigned = []
        for job_id, meta in jobs_meta.items():
            if meta.get("places"):
                loc = meta["places"][0].get("location")
                if loc:
                    unassigned.append({
                        "jobId": job_id,
                        "location": loc
                    })
        
        tours = []
        for vehicle in d.get("fleet", {}).get("vehicles", []):
            vehicle_ids = vehicle.get("vehicleIds", ["v"])
            for vid in vehicle_ids:
                for shift in vehicle.get("shifts", []):
                    start_loc = shift.get("start", {}).get("location")
                    if start_loc:
                        tours.append({
                            "vehicleId": vid,
                            "stops": [
                                {
                                    "location": start_loc,
                                    "activities": [{"type": "depot"}]
                                }
                            ]
                        })

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
    def __init__(self, problem_path, matrix_path, max_time, max_gen, updates_queue):
        super().__init__()
        self.problem_path = problem_path
        self.matrix_path = matrix_path
        self.max_time = max_time
        self.max_gen = max_gen
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
            config = Config(max_time=self.max_time, max_generations=self.max_gen)
            
            jobs_meta = _extract_jobs_meta(problem)
            self.updates_queue.put({"type": "metadata", "data": jobs_meta})
            
            start_time = time.time()
            best_cost = float('inf')
            
            def on_iteration(state, solution):
                nonlocal best_cost
                if self._stop_event.is_set():
                    # We can't cleanly abort vrp_solve yet without killing process, but we stop queueing.
                    return
                
                current_cost = solution.total_cost
                if current_cost >= best_cost:
                    return
                best_cost = current_cost
                    
                stats = solution.statistic
                times = stats.get("times", {})
                
                snapshot = {
                    "generation": state,
                    "cost": current_cost,
                    "elapsed_seconds": time.time() - start_time,
                    "tours": solution.tours,
                    "unassigned": solution.unassigned,
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
                self.updates_queue.put({"type": "iteration", "data": snapshot})
                
            vrp_solve(
                problem,
                matrices=matrices,
                config=config,
                on_iteration=on_iteration,
                every=10
            )
            
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
            
            updates_queue = queue.Queue()
            solver_thread = SolverThread(problem_path, matrix_path, max_time, max_gen, updates_queue)
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
