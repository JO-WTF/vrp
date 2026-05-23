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
    Solution,
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


class JsonAssetTest(unittest.TestCase):
    """Test JSON asset serialization and deserialization."""

    def test_problem_from_json_string(self):
        problem = Problem.from_json('{"plan": {"jobs": []}, "fleet": {"vehicles": [], "profiles": []}}')
        self.assertEqual(problem.to_dict()["plan"]["jobs"], [])

    def test_problem_from_dict(self):
        data = {"plan": {"jobs": [{"id": "job1"}]}, "fleet": {"vehicles": [], "profiles": []}}
        problem = Problem.from_dict(data)
        self.assertEqual(len(problem.to_dict()["plan"]["jobs"]), 1)

    def test_problem_to_json_roundtrip(self):
        original = Problem.empty().add_delivery("d1", (1.0, 2.0), [1])
        json_str = original.to_json()
        restored = Problem.from_json(json_str)
        self.assertEqual(restored.to_dict()["plan"]["jobs"][0]["id"], "d1")

    def test_routing_matrix_timestamp_field(self):
        matrix = RoutingMatrix(
            profile="car",
            durations=[0, 1, 1, 0],
            distances=[0, 2, 2, 0],
            timestamp="2024-01-01T00:00:00Z",
        )
        self.assertEqual(matrix.to_dict()["timestamp"], "2024-01-01T00:00:00Z")

    def test_config_from_dict(self):
        config = Config.from_dict({"termination": {"maxTime": 60, "maxGenerations": 2000}})
        data = config.to_dict()
        self.assertEqual(data["termination"]["maxTime"], 60)

    def test_solution_statistic_accessor(self):
        solution = Solution.from_dict(
            {"statistic": {"cost": 100, "distance": 50}, "tours": []}
        )
        self.assertEqual(solution.statistic.get("cost"), 100)

    def test_solution_tours_accessor(self):
        tours = [{"vehicleId": "v1", "stops": []}]
        solution = Solution.from_dict({"statistic": {}, "tours": tours})
        self.assertEqual(len(solution.tours), 1)


class ProblemBuilderTest(unittest.TestCase):
    """Test Problem builder methods."""

    def test_add_multiple_deliveries(self):
        problem = (
            Problem.empty()
            .add_delivery("d1", (1.0, 2.0), [1], duration=300)
            .add_delivery("d2", (3.0, 4.0), [2], duration=600)
        )
        jobs = problem.to_dict()["plan"]["jobs"]
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0]["id"], "d1")
        self.assertEqual(jobs[1]["id"], "d2")

    def test_add_pickup_delivery_pair(self):
        problem = Problem.empty().add_pickup_delivery(
            "pd1",
            (1.0, 2.0),
            (3.0, 4.0),
            [1],
            pickup_duration=100,
            delivery_duration=200,
        )
        job = problem.to_dict()["plan"]["jobs"][0]
        self.assertIn("pickups", job)
        self.assertIn("deliveries", job)
        self.assertEqual(len(job["pickups"]), 1)
        self.assertEqual(len(job["deliveries"]), 1)

    def test_add_vehicle_with_costs(self):
        problem = Problem.empty().add_vehicle(
            "v1",
            start_location=(1.0, 2.0),
            start_earliest="2020-01-01T09:00:00Z",
            end_latest="2020-01-01T18:00:00Z",
            capacity=[10],
            costs={"fixed": 100, "distance": 0.5, "time": 0.01},
        )
        vehicle = problem.to_dict()["fleet"]["vehicles"][0]
        self.assertEqual(vehicle["costs"]["fixed"], 100)
        self.assertEqual(vehicle["costs"]["distance"], 0.5)

    def test_add_relation(self):
        problem = (
            Problem.empty()
            .add_delivery("d1", (1.0, 2.0), [1])
            .add_relation("sequence", ["d1"], "v1")
        )
        relations = problem.to_dict()["plan"].get("relations", [])
        self.assertEqual(len(relations), 1)
        self.assertEqual(relations[0]["type"], "sequence")

    def test_set_objectives(self):
        problem = Problem.empty().set_objectives([
            [{"type": "minimize-unassigned"}],
            [{"type": "minimize-distance"}],
        ])
        objectives = problem.to_dict().get("objectives")
        self.assertEqual(len(objectives), 2)


class ConfigBuilderTest(unittest.TestCase):
    """Test Config builder methods."""

    def test_set_termination_multi_field(self):
        config = (
            Config()
            .set_termination(max_time=120, max_generations=5000)
        )
        termination = config.to_dict()["termination"]
        self.assertEqual(termination["maxTime"], 120)
        self.assertEqual(termination["maxGenerations"], 5000)

    def test_set_population_variants(self):
        config1 = Config().set_population_greedy(selection_size=4)
        config2 = Config().set_population_elitism(max_size=8, selection_size=4)
        config3 = Config().set_population_rosomaxa(selection_size=8)

        self.assertEqual(config1.to_dict()["evolution"]["population"]["type"], "greedy")
        self.assertEqual(config2.to_dict()["evolution"]["population"]["type"], "elitism")
        self.assertEqual(config3.to_dict()["evolution"]["population"]["type"], "rosomaxa")

    def test_set_hyper_static_with_operators(self):
        config = Config.defaults().set_hyper_static([
            Hyper.local_search(
                probability=Probability.scalar(0.1),
                times=min_max(1, 1),
                operators=[LocalOperator.swap_star(weight=100)],
            ),
        ])
        hyper = config.to_dict()["hyper"]
        self.assertEqual(hyper["type"], "static-selective")
        self.assertEqual(len(hyper["operators"]), 1)

    def test_config_chaining(self):
        config = (
            Config.defaults(max_time=30, max_generations=1000)
            .set_parallelism((4, 2))
            .set_experimental(True)
            .set_progress(log_best=10)
            .include_geojson()
        )
        data = config.to_dict()
        self.assertEqual(data["environment"]["parallelism"]["numThreadPools"], 4)
        self.assertTrue(data["environment"]["isExperimental"])
        self.assertEqual(data["telemetry"]["progress"]["logBest"], 10)
        self.assertTrue(data["output"]["includeGeojson"])


class RecreateRuinFactoriesTest(unittest.TestCase):
    """Test Recreate and Ruin factory methods."""

    def test_recreate_variants(self):
        methods = [
            ("cheapest", Recreate.cheapest(weight=10)),
            ("farthest", Recreate.farthest()),
            ("skip_best", Recreate.skip_best(1, 3, weight=5)),
            ("regret", Recreate.regret(2, 3, weight=15)),
            ("gaps", Recreate.gaps(2, 10)),
            ("perturbation", Recreate.perturbation(0.5, -0.1, 0.1)),
        ]
        for name, method in methods:
            self.assertIn("type", method)
            self.assertIn("weight", method)

    def test_ruin_variants(self):
        methods = [
            ("neighbour", Ruin.neighbour(0.5, 2, 8)),
            ("worst_job", Ruin.worst_job(0.5, 1, 5, skip=2)),
            ("cluster", Ruin.cluster(0.5, 3, 10)),
            ("close_route", Ruin.close_route(0.5)),
        ]
        for name, method in methods:
            self.assertIn("type", method)

    def test_ruin_group_with_methods(self):
        group = Ruin.group([
            Ruin.neighbour(0.3, 1, 5),
            Ruin.worst_job(0.3, 1, 5, skip=2),
        ], weight=10)
        self.assertIn("methods", group)
        self.assertEqual(len(group["methods"]), 2)
        self.assertEqual(group["weight"], 10)


class HyperHeuristicTest(unittest.TestCase):
    """Test hyper-heuristic configuration."""

    def test_hyper_local_search(self):
        hyper = Hyper.local_search(
            probability=Probability.scalar(0.05),
            times=min_max(1, 3),
            operators=[
                LocalOperator.swap_star(weight=100),
                LocalOperator.inter_route_best(weight=50, noise=noise(0.1, -0.05, 0.05)),
            ],
        )
        self.assertEqual(hyper["type"], "local-search")
        self.assertEqual(len(hyper["operators"]), 2)

    def test_hyper_ruin_recreate(self):
        hyper = Hyper.ruin_recreate(
            probability=Probability.scalar(0.8),
            ruins=[Ruin.neighbour(0.5, 2, 8)],
            recreates=[Recreate.cheapest(weight=20), Recreate.regret(2, 3, weight=10)],
        )
        self.assertEqual(hyper["type"], "ruin-recreate")
        self.assertEqual(len(hyper["recreates"]), 2)

    def test_probability_context(self):
        prob = Probability.context(
            jobs=100,
            routes=5,
            phases=[
                Probability.phase("exploration", 0.1),
                Probability.phase("exploitation", 0.05),
            ],
        )
        self.assertIn("threshold", prob)
        self.assertEqual(prob["threshold"]["jobs"], 100)
        self.assertEqual(len(prob["phases"]), 2)

    def test_noise_helper(self):
        n = noise(0.1, -0.05, 0.05)
        self.assertEqual(n["probability"], 0.1)
        self.assertEqual(n["min"], -0.05)
        self.assertEqual(n["max"], 0.05)


class LocationHandlingTest(unittest.TestCase):
    """Test location handling in various formats."""

    def test_location_tuple_format(self):
        problem = Problem.empty().add_delivery("d1", (52.1, 13.1), [1])
        location = problem.to_dict()["plan"]["jobs"][0]["deliveries"][0]["places"][0]["location"]
        self.assertEqual(location["lat"], 52.1)
        self.assertEqual(location["lng"], 13.1)

    def test_location_dict_format(self):
        problem = Problem.empty().add_delivery("d1", {"lat": 52.1, "lng": 13.1}, [1])
        location = problem.to_dict()["plan"]["jobs"][0]["deliveries"][0]["places"][0]["location"]
        self.assertEqual(location["lat"], 52.1)

    def test_delivery_with_time_windows(self):
        problem = Problem.empty().add_delivery(
            "d1",
            (1.0, 2.0),
            [1],
            times=[["2020-01-01T10:00:00Z", "2020-01-01T18:00:00Z"]],
        )
        job = problem.to_dict()["plan"]["jobs"][0]
        self.assertIn("times", job["deliveries"][0]["places"][0])


if __name__ == "__main__":
    unittest.main()
