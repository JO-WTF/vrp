import os
from pathlib import Path
from vrp_cli import Problem, Config, solve
from vrp_cli.vis import SolveTracker

def run() -> None:
    # 1. Load an existing pragmatic dataset from examples/data
    repo_root = Path(__file__).resolve().parents[2]
    problem_path = repo_root / "examples" / "data" / "pragmatic" / "benches" / "simple.deliveries.100.json"
    
    print(f"Loading problem from {problem_path}...")
    problem = Problem.from_json(problem_path)
    
    # 2. Setup Config (run for more generations since it's a 100-job problem)
    config = Config(max_generations=2000, max_time=15)
    config.set_population_rosomaxa()
    
    # 3. Setup Tracker — pass problem so job metadata (time windows, service
    #    duration, demand …) is embedded in the tracking JSON.
    tracker = SolveTracker(run_name="benches_simple_100", problem=problem)
    
    print("Starting solver with tracking enabled...")
    
    # 4. Solve the problem
    solution = solve(
        problem, 
        config=config,
        on_iteration=tracker.callback,
        every=10  # Rust callback frequency
    )
    
    # Ensure final data is flushed
    tracker.finish()
    
    print(f"Total cost: {solution.total_cost}")
    print("Tracking data saved! Check the dashboard at http://localhost:8080")

if __name__ == "__main__":
    run()
