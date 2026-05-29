import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from vrp_cli import Solution


def _extract_jobs_meta(problem: Any) -> Dict[str, Any]:
    """
    Extract per-job metadata (time windows, service duration, demand, location)
    from a Problem object so it can be stored alongside the history and used
    by the frontend to enrich stop tooltips.
    """
    try:
        d = problem.to_dict()
    except Exception:
        return {}

    jobs_meta: Dict[str, Any] = {}

    task_types = {
        "deliveries": "delivery",
        "pickups": "pickup",
        "services": "service",
        "replacements": "replacement",
    }

    for job in d.get("plan", {}).get("jobs", []):
        job_id = job.get("id")
        if not job_id:
            continue

        meta: Dict[str, Any] = {"type": None, "places": [], "placesByType": {}}

        for task_key in ("deliveries", "pickups", "services", "replacements"):
            tasks = job.get(task_key, [])
            if not tasks:
                continue

            task_type = task_types[task_key]
            if meta["type"] is None:
                meta["type"] = task_type

            typed_places: List[Dict[str, Any]] = []
            for task in tasks:
                place: Dict[str, Any] = {}
                loc = task.get("places", [{}])[0] if task.get("places") else {}
                place["duration"] = loc.get("duration")
                place["times"] = loc.get("times")  # list of time windows
                place["location"] = loc.get("location")
                demand = task.get("demand")
                if demand is not None:
                    place["demand"] = demand
                typed_places.append(place)
                meta["places"].append(place)

            meta["placesByType"][task_type] = typed_places

        # skills / priority / value
        if job.get("skills"):
            meta["skills"] = job["skills"]
        if job.get("priority") is not None:
            meta["priority"] = job["priority"]
        if job.get("value") is not None:
            meta["value"] = job["value"]

        jobs_meta[job_id] = meta

    return jobs_meta


class SolveTracker:
    """
    Tracks the optimization process and saves the trajectory for visualization.

    Recording policy:
    - During solving: a snapshot is saved only when a new best solution is found.
    - On finish(): one final snapshot is always appended to mark the end of the
      search, even if the last iteration produced no improvement.

    Parameters
    ----------
    run_name:
        Human-readable label stored in the JSON file.
    save_dir:
        Directory where the JSON tracking file is written.
    problem:
        Optional Problem instance. When provided, per-job metadata (time windows,
        service duration, demand …) is extracted and stored in the JSON under the
        top-level key ``"jobs_meta"``.
    """

    def __init__(
        self,
        run_name: Optional[str] = None,
        save_dir: str = ".vrp_vis_data",
        problem: Optional[Any] = None,
    ):
        self.run_name = run_name or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.save_dir = Path(save_dir)

        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.save_dir / f"{self.run_name}.json"

        self.start_time = time.time()
        self.history: List[Dict[str, Any]] = []
        self.best_cost = float("inf")
        self._last_generation: int = 0
        self._last_solution: Optional[Solution] = None

        # Extract job metadata up front so it is written into every flush.
        self._jobs_meta: Dict[str, Any] = (
            _extract_jobs_meta(problem) if problem is not None else {}
        )

    def callback(self, generation: int, solution: Solution) -> None:
        """
        To be passed as ``on_iteration`` into ``solve()``.
        Records a snapshot only when a new best solution is found.
        """
        self._last_generation = generation
        self._last_solution = solution
        current_cost = solution.total_cost

        if current_cost < self.best_cost:
            self.best_cost = current_cost
            self._record(generation, solution, is_new_best=True, flush=True)

    def finish(self) -> None:
        """
        Called after ``solve()`` completes.
        Appends one final snapshot so the dashboard always shows the
        end-of-search state, then flushes everything to disk.
        """
        if self._last_solution is not None:
            self._record(
                self._last_generation,
                self._last_solution,
                is_new_best=False,
                flush=True,
            )

    def _record(
        self,
        generation: int,
        solution: Solution,
        *,
        is_new_best: bool,
        flush: bool,
    ) -> None:
        elapsed = time.time() - self.start_time
        stat = solution.statistic or {}
        times = stat.get("times", {}) if isinstance(stat, dict) else {}

        record: Dict[str, Any] = {
            "generation": generation,
            "elapsed_seconds": round(elapsed, 3),
            "cost": solution.total_cost,
            "is_new_best": is_new_best,
            # Flat statistic fields for easy frontend consumption
            "distance": stat.get("distance"),
            "duration": stat.get("duration"),
            "driving": times.get("driving"),
            "serving": times.get("serving"),
            "waiting": times.get("waiting"),
            "break": times.get("break"),
            "commuting": times.get("commuting"),
            "parking": times.get("parking"),
            # Raw statistic dict kept for backward compatibility
            "statistic": stat,
            "num_tours": len(list(getattr(solution, "tours", []))),
            "num_unassigned": len(list(getattr(solution, "unassigned", []))),
            "tours": list(getattr(solution, "tours", [])),
            "unassigned": list(getattr(solution, "unassigned", [])),
        }
        self.history.append(record)
        if flush:
            self._flush()

    def _flush(self) -> None:
        data: Dict[str, Any] = {
            "run_name": self.run_name,
            "start_time": self.start_time,
            "end_time": time.time(),
            "jobs_meta": self._jobs_meta,
            "history": self.history,
        }

        tmp_file = self.history_file.with_suffix(self.history_file.suffix + ".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        tmp_file.replace(self.history_file)
