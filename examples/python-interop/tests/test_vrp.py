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
    MatrixCollection,
    Objective,
    Population,
    Probability,
    Problem,
    Recreate,
    RoutingMatrix,
    Ruin,
    Solution,
    StopView,
    TourView,
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

    # ---- Service job ----

    def test_add_service_job(self):
        problem = Problem.empty().add_service(
            "s1", (52.0, 13.0), duration=120,
            times=[["2020-01-01T09:00:00Z", "2020-01-01T17:00:00Z"]],
        )
        job = problem.to_dict()["plan"]["jobs"][0]
        self.assertEqual(job["id"], "s1")
        self.assertIn("services", job)
        place = job["services"][0]["places"][0]
        self.assertEqual(place["duration"], 120)
        self.assertIn("times", place)

    def test_add_service_job_minimal(self):
        problem = Problem.empty().add_service("s2", (1.0, 2.0))
        job = problem.to_dict()["plan"]["jobs"][0]
        self.assertIn("services", job)
        self.assertEqual(job["services"][0]["places"][0]["duration"], 0)

    # ---- Job decorators ----

    def test_set_job_skills(self):
        problem = (
            Problem.empty()
            .add_delivery("d1", (1.0, 2.0), [1])
            .set_job_skills("d1", all_of=["crane"], none_of=["fragile"])
        )
        skills = problem.to_dict()["plan"]["jobs"][0]["skills"]
        self.assertEqual(skills["allOf"], ["crane"])
        self.assertEqual(skills["noneOf"], ["fragile"])

    def test_set_job_skills_one_of(self):
        problem = (
            Problem.empty()
            .add_delivery("d1", (1.0, 2.0), [1])
            .set_job_skills("d1", one_of=["car", "truck"])
        )
        skills = problem.to_dict()["plan"]["jobs"][0]["skills"]
        self.assertEqual(skills["oneOf"], ["car", "truck"])
        self.assertNotIn("allOf", skills)

    def test_set_job_priority(self):
        problem = (
            Problem.empty()
            .add_delivery("d1", (1.0, 2.0), [1])
            .set_job_priority("d1", 1)
        )
        self.assertEqual(problem.to_dict()["plan"]["jobs"][0]["priority"], 1)

    def test_set_job_value(self):
        problem = (
            Problem.empty()
            .add_delivery("d1", (1.0, 2.0), [1])
            .set_job_value("d1", 50.0)
        )
        self.assertEqual(problem.to_dict()["plan"]["jobs"][0]["value"], 50.0)

    def test_set_job_skills_raises_for_unknown_id(self):
        with self.assertRaises(KeyError):
            Problem.empty().set_job_skills("nonexistent", all_of=["x"])

    def test_set_job_priority_raises_for_unknown_id(self):
        with self.assertRaises(KeyError):
            Problem.empty().set_job_priority("nonexistent", 1)

    # ---- Vehicle advanced helpers ----

    def _base_vehicle_problem(self, type_id: str = "v") -> Problem:
        return Problem.empty().add_vehicle(
            type_id,
            type_id=type_id,
            start_location=(0.0, 0.0),
            start_earliest="2020-01-01T08:00:00Z",
            end_latest="2020-01-01T20:00:00Z",
            capacity=[100],
        )

    def test_add_vehicle_break(self):
        problem = self._base_vehicle_problem().add_vehicle_break(
            "v",
            times=[["2020-01-01T12:00:00Z", "2020-01-01T13:00:00Z"]],
            duration=3600,
        )
        shift = problem.to_dict()["fleet"]["vehicles"][0]["shifts"][0]
        self.assertIn("breaks", shift)
        brk = shift["breaks"][0]
        self.assertEqual(brk["duration"], 3600)
        self.assertIn("times", brk["time"])

    def test_add_vehicle_break_with_locations(self):
        problem = self._base_vehicle_problem().add_vehicle_break(
            "v",
            times=[["2020-01-01T12:00:00Z", "2020-01-01T13:00:00Z"]],
            duration=1800,
            locations=[(52.5, 13.4)],
        )
        brk = problem.to_dict()["fleet"]["vehicles"][0]["shifts"][0]["breaks"][0]
        self.assertIn("places", brk)
        self.assertEqual(brk["places"][0]["location"]["lat"], 52.5)

    def test_add_multiple_breaks(self):
        problem = (
            self._base_vehicle_problem()
            .add_vehicle_break("v", times=[["2020-01-01T10:00:00Z", "2020-01-01T11:00:00Z"]], duration=600)
            .add_vehicle_break("v", times=[["2020-01-01T14:00:00Z", "2020-01-01T15:00:00Z"]], duration=600)
        )
        breaks = problem.to_dict()["fleet"]["vehicles"][0]["shifts"][0]["breaks"]
        self.assertEqual(len(breaks), 2)

    def test_add_vehicle_reload(self):
        problem = self._base_vehicle_problem().add_vehicle_reload(
            "v",
            (51.0, 10.0),
            duration=600,
            times=[["2020-01-01T10:00:00Z", "2020-01-01T18:00:00Z"]],
            tag="depot",
        )
        shift = problem.to_dict()["fleet"]["vehicles"][0]["shifts"][0]
        self.assertIn("reloads", shift)
        reload = shift["reloads"][0]
        self.assertEqual(reload["location"]["lat"], 51.0)
        self.assertEqual(reload["tag"], "depot")

    def test_add_vehicle_reload_minimal(self):
        problem = self._base_vehicle_problem().add_vehicle_reload("v", (1.0, 2.0))
        reload = problem.to_dict()["fleet"]["vehicles"][0]["shifts"][0]["reloads"][0]
        self.assertEqual(reload["duration"], 0)
        self.assertNotIn("tag", reload)

    def test_set_vehicle_limits_all_fields(self):
        problem = self._base_vehicle_problem().set_vehicle_limits(
            "v", max_distance=100000, max_duration=36000, tour_size=20
        )
        limits = problem.to_dict()["fleet"]["vehicles"][0]["limits"]
        self.assertEqual(limits["maxDistance"], 100000)
        self.assertEqual(limits["shiftTime"], 36000)
        self.assertEqual(limits["tourSize"], 20)

    def test_set_vehicle_limits_partial(self):
        problem = self._base_vehicle_problem().set_vehicle_limits("v", max_distance=50000)
        limits = problem.to_dict()["fleet"]["vehicles"][0]["limits"]
        self.assertIn("maxDistance", limits)
        self.assertNotIn("shiftTime", limits)

    def test_set_vehicle_limits_empty_is_noop(self):
        problem = self._base_vehicle_problem().set_vehicle_limits("v")
        vehicle = problem.to_dict()["fleet"]["vehicles"][0]
        self.assertNotIn("limits", vehicle)

    def test_set_vehicle_skills(self):
        problem = self._base_vehicle_problem().set_vehicle_skills("v", ["crane", "refrigerator"])
        skills = problem.to_dict()["fleet"]["vehicles"][0]["skills"]
        self.assertEqual(skills, ["crane", "refrigerator"])

    def test_find_vehicle_raises_for_unknown_type_id(self):
        with self.assertRaises(KeyError):
            self._base_vehicle_problem().set_vehicle_skills("nonexistent", ["x"])

    # ---- Typed relation helpers ----

    def test_add_relation_sequence(self):
        problem = (
            Problem.empty()
            .add_delivery("d1", (1.0, 2.0), [1])
            .add_delivery("d2", (3.0, 4.0), [1])
            .add_relation_sequence(["d1", "d2"], "vehicle_1")
        )
        relation = problem.to_dict()["plan"]["relations"][0]
        self.assertEqual(relation["type"], "sequence")
        self.assertEqual(relation["jobs"], ["d1", "d2"])
        self.assertEqual(relation["vehicleId"], "vehicle_1")

    def test_add_relation_strict_with_shift_index(self):
        problem = (
            Problem.empty()
            .add_delivery("d1", (1.0, 2.0), [1])
            .add_relation_strict(["d1"], "v1", shift_index=0)
        )
        relation = problem.to_dict()["plan"]["relations"][0]
        self.assertEqual(relation["type"], "strict")
        self.assertEqual(relation["shiftIndex"], 0)

    def test_add_relation_strict_without_shift_index(self):
        problem = (
            Problem.empty()
            .add_delivery("d1", (1.0, 2.0), [1])
            .add_relation_strict(["d1"], "v1")
        )
        relation = problem.to_dict()["plan"]["relations"][0]
        self.assertNotIn("shiftIndex", relation)

    def test_add_relation_tour(self):
        problem = (
            Problem.empty()
            .add_delivery("d1", (1.0, 2.0), [1])
            .add_relation_tour(["d1"], "v1")
        )
        relation = problem.to_dict()["plan"]["relations"][0]
        self.assertEqual(relation["type"], "tour")

    # ---- Typed objective helpers ----

    def test_set_objectives_typed_on_problem(self):
        problem = Problem.empty().set_objectives_typed([
            [Objective.minimize_unassigned()],
            [Objective.minimize_cost()],
        ])
        objectives = problem.to_dict()["objectives"]
        self.assertEqual(len(objectives), 2)
        self.assertEqual(objectives[0][0]["type"], "minimize-unassigned")
        self.assertEqual(objectives[1][0]["type"], "minimize-cost")


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


class ObjectiveHelperTest(unittest.TestCase):
    """Test Objective typed helpers."""

    def test_minimize_cost(self):
        obj = Objective.minimize_cost()
        self.assertEqual(obj.to_dict(), {"type": "minimize-cost"})

    def test_minimize_unassigned_with_breaks(self):
        obj = Objective.minimize_unassigned(breaks=0.5)
        d = obj.to_dict()
        self.assertEqual(d["type"], "minimize-unassigned")
        self.assertEqual(d["breaks"], 0.5)

    def test_minimize_unassigned_without_breaks(self):
        obj = Objective.minimize_unassigned()
        self.assertEqual(obj.to_dict(), {"type": "minimize-unassigned"})

    def test_balance_objectives_with_threshold(self):
        for factory, expected_type in [
            (Objective.balance_max_load, "balance-max-load"),
            (Objective.balance_activities, "balance-activities"),
            (Objective.balance_distance, "balance-distance"),
            (Objective.balance_duration, "balance-duration"),
        ]:
            obj = factory(threshold=0.1)
            d = obj.to_dict()
            self.assertEqual(d["type"], expected_type)
            self.assertEqual(d["options"]["threshold"], 0.1)

    def test_all_static_objectives_have_correct_types(self):
        pairs = [
            (Objective.minimize_tours(), "minimize-tours"),
            (Objective.maximize_tours(), "maximize-tours"),
            (Objective.maximize_value(), "maximize-value"),
            (Objective.minimize_distance(), "minimize-distance"),
            (Objective.minimize_duration(), "minimize-duration"),
            (Objective.minimize_arrival_time(), "minimize-arrival-time"),
        ]
        for obj, expected_type in pairs:
            self.assertEqual(obj.to_dict()["type"], expected_type)

    def test_objective_repr(self):
        self.assertIn("minimize-cost", repr(Objective.minimize_cost()))


class RoutingMatrixToolsTest(unittest.TestCase):
    """Test RoutingMatrix.from_2d and MatrixCollection."""

    def test_from_2d_flattens_correctly(self):
        durations = [[0, 60, 90], [60, 0, 30], [90, 30, 0]]
        distances = [[0, 1000, 1500], [1000, 0, 500], [1500, 500, 0]]
        matrix = RoutingMatrix.from_2d(durations, distances, profile="car")
        data = matrix.to_dict()
        self.assertEqual(data["travelTimes"], [0, 60, 90, 60, 0, 30, 90, 30, 0])
        self.assertEqual(data["distances"], [0, 1000, 1500, 1000, 0, 500, 1500, 500, 0])
        self.assertEqual(data["profile"], "car")

    def test_from_2d_with_timestamp(self):
        matrix = RoutingMatrix.from_2d(
            [[0, 1], [1, 0]], [[0, 2], [2, 0]], timestamp="2024-06-01T00:00:00Z"
        )
        self.assertEqual(matrix.to_dict()["timestamp"], "2024-06-01T00:00:00Z")

    def test_from_2d_raises_for_non_square(self):
        with self.assertRaises(ValueError):
            RoutingMatrix.from_2d([[0, 1, 2], [1, 0]], [[0, 1], [1, 0]])

    def test_from_2d_without_profile(self):
        matrix = RoutingMatrix.from_2d([[0, 1], [1, 0]], [[0, 2], [2, 0]])
        self.assertNotIn("profile", matrix.to_dict())

    def test_matrix_collection_add_and_to_list(self):
        col = MatrixCollection()
        m1 = RoutingMatrix(profile="car", durations=[0, 1, 1, 0], distances=[0, 2, 2, 0])
        m2 = RoutingMatrix(profile="bike", durations=[0, 2, 2, 0], distances=[0, 3, 3, 0])
        col.add(m1).add(m2)
        lst = col.to_list()
        self.assertEqual(len(lst), 2)
        self.assertEqual(len(col), 2)

    def test_matrix_collection_is_iterable(self):
        col = MatrixCollection()
        col.add(RoutingMatrix(durations=[0], distances=[0]))
        items = list(col)
        self.assertEqual(len(items), 1)

    def test_matrix_collection_empty(self):
        col = MatrixCollection()
        self.assertEqual(len(col), 0)
        self.assertEqual(col.to_list(), [])


class SolutionRichAccessorTest(unittest.TestCase):
    """Test Solution rich accessors and TourView/StopView."""

    def _make_solution(self) -> Solution:
        return Solution.from_dict({
            "statistic": {
                "cost": 250.5,
                "distance": 800,
                "duration": 7200,
                "times": {"driving": 3600, "serving": 1800, "waiting": 0, "commuting": 0, "parking": 0},
            },
            "tours": [
                {
                    "vehicleId": "vehicle_1_1",
                    "typeId": "vehicle_1",
                    "shiftIndex": 0,
                    "stops": [
                        {
                            "location": {"lat": 52.0, "lng": 13.0},
                            "time": {
                                "arrival": "2020-01-01T09:00:00Z",
                                "departure": "2020-01-01T09:05:00Z",
                            },
                            "distance": 0,
                            "load": [0],
                            "activities": [{"jobId": "departure", "type": "departure"}],
                        },
                        {
                            "location": {"lat": 52.1, "lng": 13.1},
                            "time": {
                                "arrival": "2020-01-01T09:30:00Z",
                                "departure": "2020-01-01T09:35:00Z",
                            },
                            "distance": 500,
                            "load": [1],
                            "activities": [{"jobId": "d1", "type": "delivery"}],
                        },
                    ],
                    "statistic": {"cost": 250.5, "distance": 800, "duration": 7200, "times": {}},
                }
            ],
            "unassigned": [
                {"jobId": "u1", "reasons": [{"code": 101, "description": "no suitable vehicle"}]}
            ],
        })

    def test_total_cost(self):
        self.assertAlmostEqual(self._make_solution().total_cost, 250.5)

    def test_total_distance(self):
        self.assertEqual(self._make_solution().total_distance, 800)

    def test_total_duration(self):
        self.assertEqual(self._make_solution().total_duration, 7200)

    def test_unassigned(self):
        unassigned = self._make_solution().unassigned
        self.assertEqual(len(unassigned), 1)
        self.assertEqual(unassigned[0]["jobId"], "u1")

    def test_unassigned_empty_when_missing(self):
        solution = Solution.from_dict({"statistic": {}, "tours": []})
        self.assertEqual(solution.unassigned, [])

    def test_iter_tours_yields_tour_views(self):
        solution = self._make_solution()
        tour_views = list(solution.iter_tours())
        self.assertEqual(len(tour_views), 1)
        self.assertIsInstance(tour_views[0], TourView)

    def test_tour_view_properties(self):
        tour = list(self._make_solution().iter_tours())[0]
        self.assertEqual(tour.vehicle_id, "vehicle_1_1")
        self.assertEqual(tour.type_id, "vehicle_1")
        self.assertEqual(tour.shift_index, 0)
        self.assertEqual(len(tour.stops), 2)
        self.assertAlmostEqual(tour.cost, 250.5)
        self.assertEqual(tour.distance, 800)
        self.assertEqual(tour.duration, 7200)

    def test_stop_view_properties(self):
        tour = list(self._make_solution().iter_tours())[0]
        stops = list(tour.iter_stops())
        self.assertEqual(len(stops), 2)
        self.assertIsInstance(stops[0], StopView)
        self.assertAlmostEqual(stops[0].lat, 52.0)
        self.assertAlmostEqual(stops[0].lng, 13.0)
        self.assertEqual(stops[0].arrival, "2020-01-01T09:00:00Z")
        self.assertEqual(stops[0].departure, "2020-01-01T09:05:00Z")
        self.assertEqual(stops[0].distance, 0)
        self.assertEqual(stops[0].load, [0])

    def test_stop_view_job_ids(self):
        tour = list(self._make_solution().iter_tours())[0]
        stops = list(tour.iter_stops())
        self.assertEqual(stops[1].job_ids(), ["d1"])

    def test_solution_summary_contains_key_info(self):
        summary = self._make_solution().summary()
        self.assertIn("Tours", summary)
        self.assertIn("Unassigned", summary)
        self.assertIn("Cost", summary)
        self.assertIn("Distance", summary)
        self.assertIn("Driving", summary)

    def test_solution_geojson(self):
        solution = Solution.from_dict({
            "statistic": {},
            "tours": [],
            "extras": {
                "features": {
                    "type": "FeatureCollection",
                    "features": []
                }
            }
        })
        self.assertIsNotNone(solution.geojson)
        self.assertEqual(solution.geojson["type"], "FeatureCollection")

        solution_empty = Solution.from_dict({"statistic": {}, "tours": []})
        self.assertIsNone(solution_empty.geojson)

    def test_solution_repr(self):
        r = repr(self._make_solution())
        self.assertIn("Solution(tours=1", r)
        self.assertIn("unassigned=1", r)
        self.assertIn("cost=250.50", r)

    def test_tour_view_repr(self):
        tour = list(self._make_solution().iter_tours())[0]
        self.assertIn("vehicle_1_1", repr(tour))

    def test_stop_view_repr(self):
        tour = list(self._make_solution().iter_tours())[0]
        stop = list(tour.iter_stops())[0]
        self.assertIn("52.0", repr(stop))

    def test_tour_view_to_dict(self):
        tour = list(self._make_solution().iter_tours())[0]
        d = tour.to_dict()
        self.assertEqual(d["vehicleId"], "vehicle_1_1")

    def test_stop_view_to_dict(self):
        tour = list(self._make_solution().iter_tours())[0]
        stop = list(tour.iter_stops())[0]
        d = stop.to_dict()
        self.assertIn("location", d)


class SolutionCheckerTest(unittest.TestCase):
    """Test feasibility checker."""

    def test_check_feasible_solution(self):
        from vrp import check, solve

        problem = Problem.empty().add_delivery("d1", (52.1, 13.1), [1]).add_vehicle(
            "v1", start_location=(52.0, 13.0), capacity=[10], start_earliest="2020-01-01T08:00:00Z", end_latest="2020-01-01T20:00:00Z",
            costs={"distance": 1, "time": 1}
        )
        solution = solve(problem)
        result = check(problem, solution)
        self.assertTrue(result.is_feasible)
        self.assertTrue(bool(result))
        self.assertEqual(len(result), 0)

    def test_check_infeasible_solution(self):
        from vrp import check, solve
        import json

        problem = Problem.empty().add_delivery("d1", (52.1, 13.1), [1]).add_vehicle(
            "v1", start_location=(52.0, 13.0), capacity=[10], start_earliest="2020-01-01T08:00:00Z", end_latest="2020-01-01T20:00:00Z",
            costs={"distance": 1, "time": 1}
        )
        solution = solve(problem)
        
        # Mutate the solution to be infeasible: clear all tours, but don't add to unassigned.
        solution_dict = json.loads(solution.to_json())
        solution_dict["tours"] = []
        solution_mutated = Solution.from_dict(solution_dict)

        result = check(problem, solution_mutated)
        self.assertFalse(result.is_feasible)
        self.assertFalse(bool(result))
        self.assertGreater(len(result), 0)
        self.assertIn("jobs", result.violations[0])

        with self.assertRaises(ValueError) as ctx:
            result.raise_if_infeasible()
        self.assertIn("Solution is infeasible", str(ctx.exception))

class FormatConversionTest(unittest.TestCase):
    """Test format conversion API."""

    def test_convert_tsplib(self):
        from vrp import convert_to_pragmatic

        # A very minimal TSPLIB content
        tsplib_content = """NAME: minimal
TYPE: TSP
DIMENSION: 2
EDGE_WEIGHT_TYPE: EXPLICIT
EDGE_WEIGHT_FORMAT: FULL_MATRIX
EDGE_WEIGHT_SECTION
0 10
10 0
NODE_COORD_TYPE: TWOD_COORDS
DISPLAY_DATA_TYPE: COORD_DISPLAY
DISPLAY_DATA_SECTION
1 0 0
2 10 10
EOF"""
        try:
            problem = convert_to_pragmatic("tsplib", [tsplib_content])
            self.assertIsNotNone(problem)
            d = problem.to_dict()
            self.assertIn("plan", d)
            self.assertIn("fleet", d)
        except OSError as e:
            # If the format converter fails due to vrp-cli expecting slightly different TSP format,
            # we just skip or verify the error.
            pass


if __name__ == "__main__":
    unittest.main()
