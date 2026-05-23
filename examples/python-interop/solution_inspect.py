"""
solution_inspect.py — Solution inspection example.

Demonstrates the Solution rich accessors introduced in vrp.py:
  - solution.unassigned
  - solution.total_cost / total_distance / total_duration
  - solution.summary()
  - solution.iter_tours() -> TourView
  - tour.iter_stops() -> StopView
  - stop.job_ids()
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vrp import Solution, TourView, StopView

# ---------------------------------------------------------------------------
# Build a synthetic solution (normally returned by solve())
# ---------------------------------------------------------------------------
solution = Solution.from_dict({
    "statistic": {
        "cost": 312.75,
        "distance": 1250,
        "duration": 9000,
        "times": {
            "driving": 5400,
            "serving": 2700,
            "waiting": 300,
            "commuting": 0,
            "parking": 600,
        },
    },
    "tours": [
        {
            "vehicleId": "vehicle_1_1",
            "typeId": "vehicle_1",
            "shiftIndex": 0,
            "stops": [
                {
                    "location": {"lat": 52.0, "lng": 13.0},
                    "time": {"arrival": "2020-01-01T09:00:00Z", "departure": "2020-01-01T09:00:00Z"},
                    "distance": 0,
                    "load": [0],
                    "activities": [{"jobId": "departure", "type": "departure"}],
                },
                {
                    "location": {"lat": 52.1, "lng": 13.1},
                    "time": {"arrival": "2020-01-01T09:30:00Z", "departure": "2020-01-01T09:35:00Z"},
                    "distance": 500,
                    "load": [3],
                    "activities": [{"jobId": "d1", "type": "delivery"}],
                },
                {
                    "location": {"lat": 52.2, "lng": 13.2},
                    "time": {"arrival": "2020-01-01T10:15:00Z", "departure": "2020-01-01T10:25:00Z"},
                    "distance": 1000,
                    "load": [1],
                    "activities": [
                        {"jobId": "d2", "type": "delivery"},
                        {"jobId": "p1", "type": "pickup"},
                    ],
                },
                {
                    "location": {"lat": 52.0, "lng": 13.0},
                    "time": {"arrival": "2020-01-01T11:00:00Z", "departure": "2020-01-01T11:00:00Z"},
                    "distance": 1250,
                    "load": [0],
                    "activities": [{"jobId": "arrival", "type": "arrival"}],
                },
            ],
            "statistic": {
                "cost": 312.75,
                "distance": 1250,
                "duration": 7200,
                "times": {"driving": 5400, "serving": 1800, "waiting": 0, "commuting": 0, "parking": 0},
            },
        }
    ],
    "unassigned": [
        {"jobId": "d3", "reasons": [{"code": 101, "description": "cannot be visited within time window"}]},
    ],
})

# ---------------------------------------------------------------------------
# Top-level summary
# ---------------------------------------------------------------------------
print(solution.summary())
print()
print(f"repr: {solution!r}")
print()

# ---------------------------------------------------------------------------
# Iterate tours and stops
# ---------------------------------------------------------------------------
for tour in solution.iter_tours():
    print(f"Tour: {tour.vehicle_id}  cost={tour.cost:.2f}  distance={tour.distance}  stops={len(tour.stops)}")
    for i, stop in enumerate(tour.iter_stops()):
        job_ids = stop.job_ids()
        label = ", ".join(job_ids) if job_ids else "(no jobs)"
        print(f"  Stop {i}: ({stop.lat:.3f}, {stop.lng:.3f})  "
              f"arr={stop.arrival[11:16]}  dep={stop.departure[11:16]}  "
              f"dist={stop.distance}  load={stop.load}  jobs=[{label}]")

# ---------------------------------------------------------------------------
# Unassigned jobs
# ---------------------------------------------------------------------------
print()
unassigned = solution.unassigned
print(f"Unassigned jobs ({len(unassigned)}):")
for item in unassigned:
    reasons = "; ".join(r["description"] for r in item.get("reasons", []))
    print(f"  {item['jobId']}: {reasons}")

# ---------------------------------------------------------------------------
# RoutingMatrix.from_2d example
# ---------------------------------------------------------------------------
print()
from vrp import RoutingMatrix, MatrixCollection

matrix = RoutingMatrix.from_2d(
    durations=[[0, 1800, 3600], [1800, 0, 1800], [3600, 1800, 0]],
    distances=[[0, 500, 1000], [500, 0, 500], [1000, 500, 0]],
    profile="car",
)
print(f"RoutingMatrix.from_2d: {len(matrix.to_dict()['travelTimes'])} travel time values")

col = MatrixCollection()
col.add(matrix)
col.add(RoutingMatrix(profile="bike", durations=[0, 3600, 7200, 3600, 0, 3600, 7200, 3600, 0],
                      distances=[0, 1000, 2000, 1000, 0, 1000, 2000, 1000, 0]))
print(f"MatrixCollection: {len(col)} matrices  ->  {[m.to_dict().get('profile') for m in col]}")
