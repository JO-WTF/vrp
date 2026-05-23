import argparse
import os
from pathlib import Path
from .server import serve
from .tracker import SolveTracker

def main():
    parser = argparse.ArgumentParser(description="VRP Visualization CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # serve command
    serve_parser = subparsers.add_parser("serve", help="Start the visualization server")
    serve_parser.add_argument("--port", type=int, default=8080, help="Port to serve on")
    
    # solve command
    solve_parser = subparsers.add_parser("solve", help="Solve a problem with tracking enabled")
    solve_parser.add_argument("problem", type=str, help="Path to problem JSON file")
    solve_parser.add_argument("--matrices", type=str, nargs="+", help="Paths to routing matrices JSON files")
    solve_parser.add_argument("--config", type=str, help="Path to config JSON file")
    solve_parser.add_argument("--name", type=str, help="Name of the run")
    solve_parser.add_argument("--max-time", type=int, default=60, help="Max time in seconds (if no config)")
    solve_parser.add_argument("--max-gen", type=int, default=3000, help="Max generations (if no config)")
    
    args = parser.parse_args()
    
    if args.command == "serve":
        serve(port=args.port)
    elif args.command == "solve":
        from vrp_cli import Problem, Config, RoutingMatrix, solve as vrp_solve
        
        print(f"Loading problem from {args.problem}...")
        problem = Problem.from_json(args.problem)
        
        matrices = None
        if args.matrices:
            matrices = [RoutingMatrix.from_json(m) for m in args.matrices]
            
        config = None
        if args.config:
            config = Config.from_json(args.config)
        else:
            config = Config(max_time=args.max_time, max_generations=args.max_gen)
            
        run_name = args.name or Path(args.problem).stem
        tracker = SolveTracker(run_name=run_name, problem=problem)
        
        print(f"Starting solver for run '{run_name}' with tracking enabled...")
        solution = vrp_solve(
            problem,
            matrices=matrices,
            config=config,
            on_iteration=tracker.callback,
            every=10
        )
        tracker.finish()
        
        print(f"Total cost: {solution.total_cost}")
        print(f"Tracking data saved to .vrp_vis_data/{run_name}.json")
        print("Run `uv run vrp-vis serve` to view the dashboard.")

if __name__ == "__main__":
    main()
