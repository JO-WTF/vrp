import importlib.util
import sys
import unittest
from pathlib import Path


PYTHON_INTEROP = Path(__file__).resolve().parents[1]
REPO_ROOT = PYTHON_INTEROP.parents[1]
if str(PYTHON_INTEROP) not in sys.path:
    sys.path.insert(0, str(PYTHON_INTEROP))

from vrp import Config, InitialSolution, Problem, RoutingMatrix, solve


def native_vrp_cli_available():
    return importlib.util.find_spec("vrp_cli") is not None


@unittest.skipUnless(native_vrp_cli_available(), "native vrp_cli module is not installed")
class NativeVrpCliIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.problem = Problem.from_json(REPO_ROOT / "examples/data/pragmatic/simple.basic.problem.json")
        self.matrix = RoutingMatrix.from_json(REPO_ROOT / "examples/data/pragmatic/simple.basic.matrix.json")
        self.config = Config(max_generations=1)

    def test_solve_uses_native_binding(self):
        solution = solve(self.problem, matrices=[self.matrix], config=self.config)

        self.assertIn("cost", solution.statistic)
        self.assertIsInstance(solution.tours, list)

    def test_solve_with_callback_uses_native_binding(self):
        generations = []

        def on_iteration(generation, solution):
            generations.append(generation)
            self.assertIn("cost", solution.statistic)

        solution = solve(
            self.problem,
            matrices=[self.matrix],
            config=Config(max_generations=2),
            on_iteration=on_iteration,
            every=1,
        )

        self.assertIn("cost", solution.statistic)
        self.assertTrue(generations)

    def test_solve_with_initial_solution_uses_native_binding(self):
        seed_solution = solve(self.problem, matrices=[self.matrix], config=self.config)
        solution = solve(
            self.problem,
            matrices=[self.matrix],
            config=self.config,
            initial_solution=InitialSolution(seed_solution),
        )

        self.assertIn("cost", solution.statistic)


if __name__ == "__main__":
    unittest.main()
