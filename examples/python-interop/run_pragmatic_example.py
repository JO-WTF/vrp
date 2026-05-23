import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PYTHON_INTEROP = ROOT / "examples" / "python-interop"
DATA_DIR = ROOT / "examples" / "data" / "pragmatic"

sys.path.insert(0, str(PYTHON_INTEROP))
from vrp_cli import Config, Problem, RoutingMatrix, solve  # noqa: E402


def find_example_paths(problem_path: Path, matrix_path: Path | None) -> tuple[Path, Path | None]:
    if matrix_path is not None:
        return problem_path, matrix_path

    prefix = problem_path.stem
    candidate = problem_path.with_name(f"{prefix}.matrix.json")
    if candidate.exists():
        return problem_path, candidate

    # fallback for pattern with different extension (e.g., simple.index -> simple.*.matrix.json)
    candidates = list(problem_path.parent.glob(f"{prefix}*.matrix.json"))
    if len(candidates) == 1:
        return problem_path, candidates[0]

    # second fallback: if problem has common prefix (e.g., simple.index -> simple.basic.matrix.json)
    # search for matrix files that start with the same base prefix
    if "." in prefix:
        base_prefix = prefix.split(".")[0]
        candidates = list(problem_path.parent.glob(f"{base_prefix}*.matrix.json"))
        if candidates:
            return problem_path, candidates[0]

    return problem_path, None


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def solve_example(problem_path: Path, matrix_path: Path | None, config: Config, output_path: Path | None):
    problem_data = load_json(problem_path)
    problem = Problem.from_json(problem_data)

    matrices = []
    if matrix_path is not None:
        matrix_data = load_json(matrix_path)
        matrices.append(RoutingMatrix.from_json(matrix_data))

    solution = solve(problem, matrices=matrices, config=config)

    print(f"Solved problem: {problem_path.name}")
    if matrix_path is not None:
        print(f"  matrix: {matrix_path.name}")
    print(f"  cost: {solution.statistic.get('cost')}")
    print(f"  distance: {solution.statistic.get('distance')}")
    print(f"  duration: {solution.statistic.get('duration')}")
    print(f"  tours: {len(solution.tours)}")

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(solution.to_json(), encoding="utf-8")
        print(f"  wrote solution to: {output_path}")

    return solution


def list_examples() -> list[Path]:
    return sorted(DATA_DIR.glob("**/*.problem.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a pragmatic example from examples/data/pragmatic.")
    parser.add_argument("problem", nargs="?", help="Problem JSON file path or example name in examples/data/pragmatic.")
    parser.add_argument("matrix", nargs="?", help="Optional matrix JSON file path.")
    parser.add_argument("--list", action="store_true", help="List available pragmatic examples.")
    parser.add_argument("--all", action="store_true", help="Solve all available pragmatic examples found in examples/data/pragmatic.")
    parser.add_argument("--output", help="Write the solution JSON to this file.")
    parser.add_argument("--max-time", type=int, default=30, help="Solver max_time in seconds.")
    parser.add_argument("--max-generations", type=int, default=1000, help="Solver max_generations.")
    args = parser.parse_args()

    if args.list:
        for path in list_examples():
            print(path.relative_to(DATA_DIR))
        return 0

    if args.all:
        examples = list_examples()
        if not examples:
            print("No pragmatic problem examples found.")
            return 1

        for problem_path in examples:
            matrix_path = None
            try:
                problem_path, matrix_path = find_example_paths(problem_path, None)
                solve_example(
                    problem_path,
                    matrix_path,
                    Config(max_time=args.max_time, max_generations=args.max_generations),
                    output_path=None,
                )
                print()
            except Exception as exc:
                print(f"Failed: {problem_path} -> {exc}")
                return 1
        return 0

    if args.problem is None:
        parser.print_help()
        return 1

    problem_path = Path(args.problem)
    if not problem_path.exists():
        problem_path = DATA_DIR / args.problem
        if not problem_path.exists() and problem_path.suffix == "":
            problem_path = DATA_DIR / f"{args.problem}.problem.json"

    if not problem_path.exists():
        print(f"Problem file not found: {args.problem}")
        return 1

    matrix_path = Path(args.matrix) if args.matrix else None
    problem_path, matrix_path = find_example_paths(problem_path, matrix_path)

    output_path = Path(args.output) if args.output else None
    solve_example(
        problem_path,
        matrix_path,
        Config(max_time=args.max_time, max_generations=args.max_generations),
        output_path=output_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
