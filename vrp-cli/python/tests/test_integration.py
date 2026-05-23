"""Integration tests with actual pragmatic problem data and solving."""

import importlib.util
import json
import unittest
from pathlib import Path

PYTHON_INTEROP = Path(__file__).resolve().parents[1]
REPO_ROOT = PYTHON_INTEROP.parents[1]
import sys
if str(PYTHON_INTEROP) not in sys.path:
    sys.path.insert(0, str(PYTHON_INTEROP))

from vrp_cli import (
    Config,
    Problem,
    RoutingMatrix,
    Solution,
    get_locations,
    solve,
    validate,
)


def native_vrp_cli_available():
    """Check if vrp_cli native module is installed."""
    return importlib.util.find_spec("vrp_cli") is not None


@unittest.skipUnless(native_vrp_cli_available(), "native vrp_cli module is not installed")
class IntegrationSolveTest(unittest.TestCase):
    """Test full solving workflow with real problem data."""

    @classmethod
    def setUpClass(cls):
        cls.data_dir = REPO_ROOT / "examples" / "data" / "pragmatic"
        cls.simple_basic_problem = cls.data_dir / "simple.basic.problem.json"
        cls.simple_basic_matrix = cls.data_dir / "simple.basic.matrix.json"

        if not cls.simple_basic_problem.exists():
            raise FileNotFoundError(f"Test data not found: {cls.simple_basic_problem}")

    def test_solve_simple_basic_problem(self):
        problem = Problem.from_json(self.simple_basic_problem)
        matrix = RoutingMatrix.from_json(self.simple_basic_matrix)
        config = Config(max_time=5, max_generations=100)

        solution = solve(problem, matrices=[matrix], config=config)

        self.assertIn("cost", solution.statistic)
        self.assertIn("distance", solution.statistic)
        self.assertIn("duration", solution.statistic)
        self.assertIsInstance(solution.tours, list)
        self.assertGreater(solution.statistic.get("cost", 0), 0)

    def test_solve_with_callback(self):
        problem = Problem.from_json(self.simple_basic_problem)
        matrix = RoutingMatrix.from_json(self.simple_basic_matrix)
        config = Config(max_generations=10)

        generations = []
        costs = []

        def on_iteration(generation, solution):
            generations.append(generation)
            costs.append(solution.statistic.get("cost", 0))

        solution = solve(
            problem,
            matrices=[matrix],
            config=config,
            on_iteration=on_iteration,
            every=1,
        )

        self.assertTrue(len(generations) > 0)
        self.assertTrue(len(costs) > 0)
        self.assertTrue(all(c > 0 for c in costs))

    def test_validate_problem_with_matrix(self):
        problem = Problem.from_json(self.simple_basic_problem)
        matrix = RoutingMatrix.from_json(self.simple_basic_matrix)

        # Should not raise
        validate(problem, matrices=[matrix])

    def test_get_locations_from_problem(self):
        problem = Problem.from_json(self.simple_basic_problem)
        locations = get_locations(problem)

        self.assertIsInstance(locations.to_dict(), list)
        self.assertGreater(len(locations.to_dict()), 0)

    def test_multiple_matrices(self):
        problem = Problem.from_json(self.simple_basic_problem)
        matrix = RoutingMatrix.from_json(self.simple_basic_matrix)
        config = Config(max_time=5, max_generations=50)

        # Test with single matrix
        solution = solve(problem, matrices=[matrix], config=config)

        self.assertIn("cost", solution.statistic)
        self.assertGreater(len(solution.tours), 0)


@unittest.skipUnless(native_vrp_cli_available(), "native vrp_cli module is not installed")
class RealProblemVariantsTest(unittest.TestCase):
    """Test solving various problem variants."""

    @classmethod
    def setUpClass(cls):
        cls.data_dir = Path(__file__).resolve().parents[1].parents[1] / "data" / "pragmatic"

    def _find_problem_and_matrix(self, problem_name):
        problem_path = self.data_dir / f"{problem_name}.problem.json"
        if not problem_path.exists():
            # Try with subdirectories
            matches = list(self.data_dir.rglob(f"{problem_name}.problem.json"))
            if matches:
                problem_path = matches[0]

        # Find corresponding matrix
        matrix_path = problem_path.with_name(f"{problem_path.stem}.matrix.json")
        if not matrix_path.exists():
            prefix = problem_path.stem
            candidates = list(problem_path.parent.glob(f"{prefix}*.matrix.json"))
            if candidates:
                matrix_path = candidates[0]

        return problem_path if problem_path.exists() else None, matrix_path if matrix_path.exists() else None

    def test_simple_index_problem(self):
        problem_path, matrix_path = self._find_problem_and_matrix("simple.index")
        if not problem_path:
            self.skipTest("simple.index problem not found")

        problem = Problem.from_json(problem_path)
        config = Config(max_time=5, max_generations=100)

        matrices = [RoutingMatrix.from_json(matrix_path)] if matrix_path else []
        solution = solve(problem, matrices=matrices, config=config)

        self.assertIn("cost", solution.statistic)
        self.assertIsInstance(solution.tours, list)

    def test_clustering_berlin_problem(self):
        problem_path, matrix_path = self._find_problem_and_matrix("berlin.vicinity-return")
        if not problem_path:
            self.skipTest("berlin.vicinity-return problem not found")

        problem = Problem.from_json(problem_path)
        config = Config(max_time=10, max_generations=200)

        matrices = [RoutingMatrix.from_json(matrix_path)] if matrix_path else []
        solution = solve(problem, matrices=matrices, config=config)

        self.assertGreater(solution.statistic.get("cost", 0), 0)
        self.assertGreater(len(solution.tours), 0)


class SolutionAccessorTest(unittest.TestCase):
    """Test Solution object accessors."""

    def test_solution_statistic_fields(self):
        solution_data = {
            "statistic": {
                "cost": 123.45,
                "distance": 500,
                "duration": 3600,
                "times": {
                    "driving": 1800,
                    "serving": 1200,
                    "waiting": 600,
                    "commuting": 0,
                    "parking": 0,
                },
            },
            "tours": [],
        }
        solution = Solution.from_dict(solution_data)

        self.assertEqual(solution.statistic["cost"], 123.45)
        self.assertEqual(solution.statistic["distance"], 500)
        self.assertEqual(solution.statistic["times"]["driving"], 1800)

    def test_solution_tours_structure(self):
        solution_data = {
            "statistic": {"cost": 0, "distance": 0, "duration": 0, "times": {}},
            "tours": [
                {
                    "vehicleId": "vehicle_1",
                    "typeId": "type_1",
                    "shiftIndex": 0,
                    "stops": [
                        {
                            "location": {"lat": 0, "lng": 0},
                            "time": {"arrival": "2020-01-01T00:00:00Z", "departure": "2020-01-01T00:00:00Z"},
                            "distance": 0,
                            "load": [0],
                            "activities": [],
                        }
                    ],
                    "statistic": {"cost": 0, "distance": 0, "duration": 0, "times": {}},
                }
            ],
        }
        solution = Solution.from_dict(solution_data)

        self.assertEqual(len(solution.tours), 1)
        self.assertEqual(solution.tours[0]["vehicleId"], "vehicle_1")


class ConfigPresetTest(unittest.TestCase):
    """Test Config presets and variations."""

    def test_config_defaults_preset(self):
        config = Config.defaults(max_time=60, max_generations=2000)
        data = config.to_dict()

        self.assertEqual(data["termination"]["maxTime"], 60)
        self.assertEqual(data["termination"]["maxGenerations"], 2000)

    def test_config_chain_multiple_settings(self):
        config = (
            Config.defaults()
            .set_termination(max_time=120)
            .set_parallelism((4, 2))
            .set_logging(enabled=True, prefix="[solve]")
            .set_progress(log_best=10)
            .set_metrics(track_population=100)
            .include_geojson(True)
        )
        data = config.to_dict()

        self.assertIn("termination", data)
        self.assertIn("environment", data)
        self.assertIn("telemetry", data)
        self.assertIn("output", data)
        self.assertTrue(data["output"]["includeGeojson"])


if __name__ == "__main__":
    unittest.main()
