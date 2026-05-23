from pathlib import Path

from vrp_cli import Config, InitialSolution, Problem, RoutingMatrix, solve


ROOT = Path(__file__).resolve().parents[2]

problem = Problem.from_json(ROOT / "examples/data/pragmatic/simple.basic.problem.json")
matrix = RoutingMatrix.from_json(ROOT / "examples/data/pragmatic/simple.basic.matrix.json")

# Initial solutions use the pragmatic solution format. In a real workflow, this
# can come from a previous solve result or a saved solution JSON file.
initial_solution = InitialSolution(
    {
        "statistic": {
            "cost": 0,
            "distance": 0,
            "duration": 0,
            "times": {"driving": 0, "serving": 0, "waiting": 0, "commuting": 0, "parking": 0},
        },
        "tours": [],
        "unassigned": [],
    }
)

config = Config(max_time=5, max_generations=1000)

solution = solve(problem, matrices=[matrix], config=config, initial_solution=initial_solution)
print(solution.statistic)
