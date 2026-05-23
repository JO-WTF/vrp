"""
objectives.py — Typed objective helpers example.

Demonstrates how to use the Objective class to configure
various pragmatic optimization objectives.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vrp import Config, Objective, Problem

# ---------------------------------------------------------------------------
# Build a simple problem
# ---------------------------------------------------------------------------
problem = (
    Problem.empty()
    .add_delivery("d1", (52.1, 13.1), [1], duration=300)
    .add_delivery("d2", (52.2, 13.2), [2], duration=600)
    .add_vehicle(
        "vehicle_1",
        start_location=(52.0, 13.0),
        start_earliest="2020-01-01T09:00:00Z",
        end_latest="2020-01-01T18:00:00Z",
        capacity=[10],
    )
)

# ---------------------------------------------------------------------------
# Example 1: Single-objective — minimize cost (default pragmatic behaviour)
# ---------------------------------------------------------------------------
problem_cost = problem.set_objectives_typed([
    [Objective.minimize_cost()],
])
print("Example 1 — minimize cost:")
print(problem_cost.to_json(indent=2)[-200:])  # show tail of JSON
print()

# ---------------------------------------------------------------------------
# Example 2: Lexicographic — first minimize unassigned, then minimize cost
# ---------------------------------------------------------------------------
problem_lex = Problem.from_dict(problem.to_dict()).set_objectives_typed([
    [Objective.minimize_unassigned()],
    [Objective.minimize_cost()],
])
print("Example 2 — minimize unassigned > cost (lexicographic):")
for i, group in enumerate(problem_lex.to_dict()["objectives"]):
    print(f"  Priority {i+1}: {[o['type'] for o in group]}")
print()

# ---------------------------------------------------------------------------
# Example 3: Multi-criteria — minimize tours + balance max load
# ---------------------------------------------------------------------------
problem_multi = Problem.from_dict(problem.to_dict()).set_objectives_typed([
    [Objective.minimize_unassigned()],
    [Objective.minimize_tours(), Objective.balance_max_load(threshold=0.1)],
])
print("Example 3 — minimize tours + balance max load:")
for i, group in enumerate(problem_multi.to_dict()["objectives"]):
    print(f"  Priority {i+1}: {[o['type'] for o in group]}")
print()

# ---------------------------------------------------------------------------
# Example 4: Maximize value (job-value-weighted objectives)
# ---------------------------------------------------------------------------
problem_value = (
    Problem.empty()
    .add_delivery("high_value", (52.1, 13.1), [1])
    .add_delivery("low_value", (52.2, 13.2), [1])
    .set_job_value("high_value", 100.0)
    .set_job_value("low_value", 10.0)
    .add_vehicle(
        "v1",
        start_location=(52.0, 13.0),
        start_earliest="2020-01-01T09:00:00Z",
        end_latest="2020-01-01T18:00:00Z",
        capacity=[1],  # can only serve one job
    )
    .set_objectives_typed([
        [Objective.maximize_value()],
    ])
)
print("Example 4 — maximize value (job values: high=100, low=10):")
objectives = problem_value.to_dict().get("objectives", [])
print(f"  Objectives: {[[o['type'] for o in g] for g in objectives]}")
print(f"  Job values: {[j.get('value') for j in problem_value.to_dict()['plan']['jobs']]}")

print("\nAll objective examples constructed successfully.")
