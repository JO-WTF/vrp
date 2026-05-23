"""
relations.py — Typed relation helpers example.

Demonstrates how to use add_relation_sequence, add_relation_strict,
and add_relation_tour to constrain vehicle routing plans.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vrp import Problem


def _base_problem() -> Problem:
    return (
        Problem.empty()
        .add_delivery("d1", (52.10, 13.10), [1], duration=300)
        .add_delivery("d2", (52.20, 13.20), [1], duration=300)
        .add_delivery("d3", (52.30, 13.30), [1], duration=300)
        .add_vehicle(
            "vehicle_1",
            start_location=(52.00, 13.00),
            start_earliest="2020-01-01T09:00:00Z",
            end_latest="2020-01-01T18:00:00Z",
            capacity=[10],
        )
    )


# ---------------------------------------------------------------------------
# Example 1: Sequence — d1 must be served before d2, but not necessarily
#            consecutively and not necessarily on the same vehicle.
# ---------------------------------------------------------------------------
problem_seq = _base_problem().add_relation_sequence(["d1", "d2"], "vehicle_1")
relations = problem_seq.to_dict()["plan"]["relations"]
print("Example 1 — sequence relation:")
for r in relations:
    print(f"  type={r['type']!r}  jobs={r['jobs']}  vehicle={r['vehicleId']!r}")
print()

# ---------------------------------------------------------------------------
# Example 2: Strict — d1 → d2 must be served consecutively on vehicle_1,
#            optionally on a specific shift.
# ---------------------------------------------------------------------------
problem_strict = _base_problem().add_relation_strict(["d1", "d2"], "vehicle_1", shift_index=0)
relations = problem_strict.to_dict()["plan"]["relations"]
print("Example 2 — strict relation (shift 0):")
for r in relations:
    print(f"  type={r['type']!r}  jobs={r['jobs']}  vehicle={r['vehicleId']!r}  shiftIndex={r.get('shiftIndex')}")
print()

# ---------------------------------------------------------------------------
# Example 3: Tour — d3 must be served by vehicle_1 (any order, exclusive).
# ---------------------------------------------------------------------------
problem_tour = _base_problem().add_relation_tour(["d3"], "vehicle_1")
relations = problem_tour.to_dict()["plan"]["relations"]
print("Example 3 — tour relation:")
for r in relations:
    print(f"  type={r['type']!r}  jobs={r['jobs']}  vehicle={r['vehicleId']!r}")
print()

# ---------------------------------------------------------------------------
# Example 4: Vehicle break + reload constraints (advanced vehicle helpers)
# ---------------------------------------------------------------------------
problem_adv = (
    _base_problem()
    # Mandatory lunch break between noon and 1pm
    .add_vehicle_break(
        "vehicle",
        times=[["2020-01-01T12:00:00Z", "2020-01-01T13:00:00Z"]],
        duration=3600,
    )
    # Reload point to refill capacity mid-route
    .add_vehicle_reload(
        "vehicle",
        (52.05, 13.05),
        duration=600,
        tag="depot",
    )
    # Limit total tour distance
    .set_vehicle_limits("vehicle", max_distance=200_000)
    # Require skills
    .set_vehicle_skills("vehicle", ["refrigerator"])
)
vehicle = problem_adv.to_dict()["fleet"]["vehicles"][0]
shift = vehicle["shifts"][0]
print("Example 4 — vehicle breaks, reloads, limits, skills:")
print(f"  breaks  : {len(shift.get('breaks', []))} defined")
print(f"  reloads : {len(shift.get('reloads', []))} defined")
print(f"  limits  : {vehicle.get('limits')}")
print(f"  skills  : {vehicle.get('skills')}")

print("\nAll relation examples constructed successfully.")
