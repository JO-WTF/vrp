import sys
import types
import unittest
from pathlib import Path


PYTHON_INTEROP = Path(__file__).resolve().parents[1]
if str(PYTHON_INTEROP) not in sys.path:
    sys.path.insert(0, str(PYTHON_INTEROP))

from vrp import (
    Config,
    Hyper,
    InitialSolution,
    LocalOperator,
    Population,
    Probability,
    Problem,
    Recreate,
    RoutingMatrix,
    Ruin,
    min_max,
    noise,
    solve,
)


class VrpFacadeTest(unittest.TestCase):
    def test_routing_matrix_uses_python_durations_api(self):
        matrix = RoutingMatrix(
            profile="car",
            durations=[0, 1, 1, 0],
            distances=[0, 2, 2, 0],
        )

        self.assertEqual(matrix.to_dict()["travelTimes"], [0, 1, 1, 0])
        self.assertNotIn("durations", matrix.to_dict())

    def test_config_builder_serializes_camel_case_fields(self):
        config = (
            Config.defaults(max_time=10, max_generations=20)
            .set_variation("sample", 100, 0.2)
            .set_parallelism((2, 4))
            .set_logging(prefix="[py]")
            .set_progress(log_best=5)
            .set_metrics(track_population=50)
            .include_geojson()
            .set_population_rosomaxa(selection_size=8, max_elite_size=2)
            .set_hyper_dynamic()
        )

        data = config.to_dict()
        self.assertEqual(data["termination"]["variation"]["intervalType"], "sample")
        self.assertEqual(data["environment"]["parallelism"]["threadsPerPool"], 4)
        self.assertEqual(data["telemetry"]["progress"]["logBest"], 5)
        self.assertTrue(data["output"]["includeGeojson"])
        self.assertEqual(data["evolution"]["population"]["type"], "rosomaxa")
        self.assertEqual(data["hyper"]["type"], "dynamic-selective")

    def test_config_initial_and_population_helpers(self):
        config = (
            Config.defaults()
            .set_initial(
                Recreate.cheapest(weight=1),
                alternatives=[
                    Recreate.farthest(weight=2),
                    Recreate.regret(2, 3, weight=3),
                    Recreate.skip_best(1, 2),
                    Recreate.gaps(2, 20),
                    Recreate.perturbation(0.33, -0.2, 0.2),
                ],
                max_size=4,
                quota=0.05,
            )
            .set_evolution(population=Population.elitism(max_size=4, selection_size=8))
        )

        evolution = config.to_dict()["evolution"]
        self.assertEqual(evolution["initial"]["method"], {"type": "cheapest", "weight": 1})
        self.assertEqual(evolution["initial"]["alternatives"]["maxSize"], 4)
        self.assertEqual(evolution["initial"]["alternatives"]["methods"][1]["type"], "regret")
        self.assertEqual(evolution["population"]["type"], "elitism")
        self.assertEqual(evolution["population"]["selectionSize"], 8)

    def test_hyper_helpers_serialize_nested_operator_tree(self):
        config = Config.defaults().set_hyper_static(
            [
                Hyper.local_search(
                    probability=Probability.scalar(0.05),
                    times=min_max(1, 2),
                    operators=[
                        LocalOperator.swap_star(weight=200),
                        LocalOperator.inter_route_best(weight=100, noise=noise(0.1, -0.1, 0.1)),
                    ],
                ),
                Hyper.ruin_recreate(
                    probability=Probability.context(
                        jobs=300,
                        routes=10,
                        phases=[
                            Probability.phase("exploration", 0.05),
                            Probability.phase("exploitation", 0.05),
                        ],
                    ),
                    ruins=[
                        Ruin.group(
                            [
                                Ruin.neighbour(1, 8, 16),
                                Ruin.worst_job(1, 8, 16, skip=4),
                            ],
                            weight=10,
                        )
                    ],
                    recreates=[Recreate.cheapest(weight=20), Recreate.skip_best(1, 2, weight=10)],
                ),
            ]
        )

        operators = config.to_dict()["hyper"]["operators"]
        self.assertEqual(operators[0]["type"], "local-search")
        self.assertEqual(operators[0]["operators"][1]["noise"]["probability"], 0.1)
        self.assertEqual(operators[1]["type"], "ruin-recreate")
        self.assertEqual(operators[1]["probability"]["threshold"]["jobs"], 300)
        self.assertEqual(operators[1]["ruins"][0]["methods"][1]["type"], "worst-job")

    def test_problem_builder_serializes_basic_problem(self):
        problem = (
            Problem.empty()
            .add_delivery("delivery", (52.1, 13.1), [1], duration=300)
            .add_vehicle(
                "vehicle_1",
                start_location=(52.0, 13.0),
                start_earliest="2020-01-01T09:00:00Z",
                end_latest="2020-01-01T18:00:00Z",
                capacity=[10],
            )
        )

        data = problem.to_dict()
        self.assertEqual(data["plan"]["jobs"][0]["id"], "delivery")
        self.assertEqual(data["plan"]["jobs"][0]["deliveries"][0]["demand"], [1])
        self.assertEqual(data["fleet"]["vehicles"][0]["vehicleIds"], ["vehicle_1"])
        self.assertEqual(data["fleet"]["profiles"][0]["name"], "normal_car")

    def test_solve_with_initial_solution_uses_init_binding(self):
        fake_vrp_cli = types.SimpleNamespace()
        calls = []

        def solve_pragmatic_with_init(**kwargs):
            calls.append(kwargs)
            return '{"statistic": {}, "tours": []}'

        fake_vrp_cli.solve_pragmatic_with_init = solve_pragmatic_with_init
        previous = sys.modules.get("vrp_cli")
        sys.modules["vrp_cli"] = fake_vrp_cli
        try:
            solution = solve(
                Problem.empty(),
                config=Config(max_generations=1),
                initial_solution=InitialSolution({"statistic": {}, "tours": []}),
            )
        finally:
            if previous is None:
                sys.modules.pop("vrp_cli", None)
            else:
                sys.modules["vrp_cli"] = previous

        self.assertEqual(solution.tours, [])
        self.assertEqual(len(calls), 1)
        self.assertIn("init_solution", calls[0])


if __name__ == "__main__":
    unittest.main()
