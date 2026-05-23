"""
Example demonstrating how to track optimization runs for the web visualizer.
"""

from vrp_cli import Problem, Config, solve
from vrp_cli.vis import SolveTracker

def run() -> None:
    # 1. Create a larger problem so the optimization process takes a few seconds
    # and generates interesting convergence data.
    problem = (
        Problem.empty()
        .add_vehicle(
            "vehicle_1",
            type_id="vehicle_type_1",
            start_location=(0, 0),
            start_earliest="2024-01-01T08:00:00Z",
            capacity=[100],
            costs={"distance": 1, "time": 1},
        )
        .add_vehicle(
            "vehicle_2",
            type_id="vehicle_type_2",
            start_location=(10, 10),
            start_earliest="2024-01-01T08:00:00Z",
            capacity=[100],
            costs={"distance": 1, "time": 1},
        )
    )
    
    # Add 50 random jobs
    import random
    for i in range(50):
        problem.add_delivery(
            f"job_{i}", 
            (random.uniform(0, 10), random.uniform(0, 10)), 
            demand=[random.randint(1, 5)]
        )

    # 2. Setup Config (run for at least 1000 generations)
    config = Config(max_generations=1000, max_time=10)
    config.set_population_rosomaxa(exploration_ratio=0.8) # Encourage exploration to make the graph interesting

    # 3. Setup Tracker
    tracker = SolveTracker(run_name="example_run")
    
    print("Starting solver with tracking enabled...")
    
    # 4. Solve the problem with the tracker's callback
    # `every=10` means the Rust engine will invoke the callback every 10 generations.
    solution = solve(
        problem, 
        config=config,
        on_iteration=tracker.callback,
        every=10
    )
    
    # Ensure final data is flushed to disk
    tracker.finish()
    
    print(f"Total cost: {solution.total_cost}")
    print("Tracking data saved! To view the dashboard, run:")
    print("uv run vrp-vis serve")

if __name__ == "__main__":
    run()
