from pathlib import Path

from vrp import Config, Problem, RoutingMatrix, solve


ROOT = Path(__file__).resolve().parents[2]

problem = Problem.from_json(ROOT / "examples/data/pragmatic/simple.basic.problem.json")
matrix = RoutingMatrix.from_json(ROOT / "examples/data/pragmatic/simple.basic.matrix.json")
config = Config.from_json(ROOT / "examples/data/config/config.full.json")

solution = solve(problem, matrices=[matrix], config=config)
print(solution.statistic)
