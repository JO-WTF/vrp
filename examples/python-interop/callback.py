from pathlib import Path

from vrp_cli import Config, Problem, RoutingMatrix, solve


ROOT = Path(__file__).resolve().parents[2]

problem = Problem.from_json(ROOT / "examples/data/pragmatic/simple.basic.problem.json")
matrix = RoutingMatrix.from_json(ROOT / "examples/data/pragmatic/simple.basic.matrix.json")
config = Config(max_time=5, max_generations=1000)


def on_iteration(generation, solution):
    statistic = solution.statistic
    print(
        "iteration callback:",
        f"generation={generation}",
        f"cost={statistic.get('cost')}",
        f"routes={len(solution.tours)}",
    )


solution = solve(problem, matrices=[matrix], config=config, on_iteration=on_iteration, every=100)
print(solution.statistic)
