from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Union

try:
    from pydantic.json import pydantic_encoder
except ImportError:
    pydantic_encoder = None


JsonData = Union[Dict[str, Any], List[Any]]
JsonInput = Union[str, Path, JsonData, Any]
IterationCallback = Callable[[int, "Solution"], None]


class JsonAsset:
    """Base class for pragmatic JSON assets."""

    def __init__(self, data: JsonData):
        self._data = _to_jsonable(data) if not isinstance(data, (dict, list)) else deepcopy(data)

    @classmethod
    def from_json(cls, source: JsonInput):
        return cls(_read_json(source))

    @classmethod
    def from_dict(cls, data: JsonData):
        return cls(data)

    def to_dict(self) -> JsonData:
        return deepcopy(self._data)

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self._data, default=_json_default, **kwargs)

    def write_json(self, path: Union[str, Path], **kwargs: Any) -> None:
        Path(path).write_text(self.to_json(**kwargs), encoding="utf-8")


class Problem(JsonAsset):
    """Pragmatic problem definition asset."""

    @classmethod
    def empty(cls) -> "Problem":
        return cls({"plan": {"jobs": []}, "fleet": {"vehicles": [], "profiles": []}})

    def get_locations(self) -> "RoutingLocations":
        import vrp_cli

        return RoutingLocations.from_json(vrp_cli.get_routing_locations(self.to_json()))

    def validate(self, matrices: Optional[Iterable[JsonInput]] = None) -> None:
        validate(self, matrices)

    def add_delivery(
        self,
        job_id: str,
        location: Any,
        demand: Sequence[int],
        *,
        duration: Union[int, float] = 0,
        times: Optional[Sequence[Sequence[str]]] = None,
        tag: Optional[str] = None,
        **extra: Any,
    ) -> "Problem":
        return self._add_job_task(job_id, "deliveries", location, demand, duration=duration, times=times, tag=tag, **extra)

    def add_pickup(
        self,
        job_id: str,
        location: Any,
        demand: Sequence[int],
        *,
        duration: Union[int, float] = 0,
        times: Optional[Sequence[Sequence[str]]] = None,
        tag: Optional[str] = None,
        **extra: Any,
    ) -> "Problem":
        return self._add_job_task(job_id, "pickups", location, demand, duration=duration, times=times, tag=tag, **extra)

    def add_pickup_delivery(
        self,
        job_id: str,
        pickup_location: Any,
        delivery_location: Any,
        demand: Sequence[int],
        *,
        pickup_duration: Union[int, float] = 0,
        delivery_duration: Union[int, float] = 0,
        pickup_times: Optional[Sequence[Sequence[str]]] = None,
        delivery_times: Optional[Sequence[Sequence[str]]] = None,
        pickup_tag: Optional[str] = None,
        delivery_tag: Optional[str] = None,
        **extra: Any,
    ) -> "Problem":
        job = {
            "id": job_id,
            "pickups": [
                _task(
                    pickup_location,
                    demand,
                    duration=pickup_duration,
                    times=pickup_times,
                    tag=pickup_tag,
                )
            ],
            "deliveries": [
                _task(
                    delivery_location,
                    demand,
                    duration=delivery_duration,
                    times=delivery_times,
                    tag=delivery_tag,
                )
            ],
        }
        job.update(extra)
        self._jobs().append(job)
        return self

    def add_vehicle(
        self,
        vehicle_id: str,
        *,
        type_id: str = "vehicle",
        profile: str = "normal_car",
        start_location: Any,
        start_earliest: str,
        end_location: Optional[Any] = None,
        end_latest: Optional[str] = None,
        capacity: Sequence[int],
        costs: Optional[Dict[str, Union[int, float]]] = None,
        vehicle_ids: Optional[Sequence[str]] = None,
        **extra: Any,
    ) -> "Problem":
        vehicle = {
            "typeId": type_id,
            "vehicleIds": list(vehicle_ids or [vehicle_id]),
            "profile": {"matrix": profile},
            "costs": costs or {"fixed": 0, "distance": 0, "time": 0},
            "shifts": [
                {
                    "start": {
                        "earliest": start_earliest,
                        "location": _location(start_location),
                    },
                    "end": {
                        "latest": end_latest or start_earliest,
                        "location": _location(end_location or start_location),
                    },
                }
            ],
            "capacity": list(capacity),
        }
        vehicle.update(extra)
        self._vehicles().append(vehicle)
        self.add_profile(profile)
        return self

    def add_profile(self, name: str, **extra: Any) -> "Problem":
        profiles = self._profiles()
        if not any(profile.get("name") == name for profile in profiles):
            profile = {"name": name}
            profile.update(extra)
            profiles.append(profile)
        return self

    def add_relation(self, relation_type: str, jobs: Sequence[str], vehicle_id: str, **extra: Any) -> "Problem":
        relation = {"type": relation_type, "jobs": list(jobs), "vehicleId": vehicle_id}
        relation.update(extra)
        self._data.setdefault("plan", {}).setdefault("relations", []).append(relation)
        return self

    def set_objectives(self, objectives: Sequence[Sequence[Dict[str, Any]]]) -> "Problem":
        self._data["objectives"] = deepcopy(objectives)
        return self

    def _add_job_task(
        self,
        job_id: str,
        task_type: str,
        location: Any,
        demand: Sequence[int],
        *,
        duration: Union[int, float],
        times: Optional[Sequence[Sequence[str]]],
        tag: Optional[str],
        **extra: Any,
    ) -> "Problem":
        job = {"id": job_id, task_type: [_task(location, demand, duration=duration, times=times, tag=tag)]}
        job.update(extra)
        self._jobs().append(job)
        return self

    def _jobs(self) -> List[Dict[str, Any]]:
        return self._data.setdefault("plan", {}).setdefault("jobs", [])

    def _vehicles(self) -> List[Dict[str, Any]]:
        return self._data.setdefault("fleet", {}).setdefault("vehicles", [])

    def _profiles(self) -> List[Dict[str, Any]]:
        return self._data.setdefault("fleet", {}).setdefault("profiles", [])


class RoutingLocations(JsonAsset):
    """Ordered unique locations used to request routing matrices."""


class RoutingMatrix(JsonAsset):
    """Pragmatic routing matrix asset."""

    def __init__(
        self,
        data: Optional[JsonData] = None,
        *,
        profile: Optional[str] = None,
        durations: Optional[Sequence[Union[int, float]]] = None,
        distances: Optional[Sequence[Union[int, float]]] = None,
        timestamp: Optional[str] = None,
    ):
        if data is None:
            if durations is None or distances is None:
                raise ValueError("durations and distances are required when data is not specified")

            data = {
                "travelTimes": list(durations),
                "distances": list(distances),
            }

            if profile is not None:
                data["profile"] = profile
            if timestamp is not None:
                data["timestamp"] = timestamp
        else:
            data = _to_jsonable(data) if not isinstance(data, (dict, list)) else deepcopy(data)

        if isinstance(data, dict) and "durations" in data and "travelTimes" not in data:
            data["travelTimes"] = data.pop("durations")

        super().__init__(data)

    @classmethod
    def from_json(cls, source: JsonInput) -> "RoutingMatrix":
        return cls(_read_json(source))

    @classmethod
    def from_dict(cls, data: JsonData) -> "RoutingMatrix":
        return cls(data)


class Config(JsonAsset):
    """Solver configuration asset."""

    def __init__(
        self,
        data: Optional[JsonData] = None,
        *,
        max_time: Optional[int] = None,
        max_generations: Optional[int] = None,
        parallelism: Optional[Union[int, Sequence[int], Dict[str, int]]] = None,
        include_geojson: Optional[bool] = None,
        evolution: Optional[Dict[str, Any]] = None,
        hyper: Optional[Dict[str, Any]] = None,
        termination: Optional[Dict[str, Any]] = None,
        telemetry: Optional[Dict[str, Any]] = None,
        environment: Optional[Dict[str, Any]] = None,
        output: Optional[Dict[str, Any]] = None,
    ):
        if data is None:
            data = {}

            termination = dict(termination or {})
            if max_time is not None:
                termination["maxTime"] = max_time
            if max_generations is not None:
                termination["maxGenerations"] = max_generations
            if termination:
                data["termination"] = termination

            environment = dict(environment or {})
            if parallelism is not None:
                environment["parallelism"] = _normalize_parallelism(parallelism)
            if environment:
                data["environment"] = environment

            output = dict(output or {})
            if include_geojson is not None:
                output["includeGeojson"] = include_geojson
            if output:
                data["output"] = output

            if evolution is not None:
                data["evolution"] = evolution
            if hyper is not None:
                data["hyper"] = hyper
            if telemetry is not None:
                data["telemetry"] = telemetry

        super().__init__(data)

    @classmethod
    def from_json(cls, source: JsonInput) -> "Config":
        return cls(_read_json(source))

    @classmethod
    def from_dict(cls, data: JsonData) -> "Config":
        return cls(data)

    @classmethod
    def defaults(cls, *, max_time: int = 300, max_generations: int = 3000) -> "Config":
        return cls(max_time=max_time, max_generations=max_generations)

    def set_termination(
        self,
        *,
        max_time: Optional[int] = None,
        max_generations: Optional[int] = None,
        variation: Optional[Dict[str, Any]] = None,
    ) -> "Config":
        termination = self._data.setdefault("termination", {})
        if max_time is not None:
            termination["maxTime"] = max_time
        if max_generations is not None:
            termination["maxGenerations"] = max_generations
        if variation is not None:
            termination["variation"] = deepcopy(variation)
        return self

    def set_variation(self, interval_type: str, value: int, cv: float, *, is_global: bool = True) -> "Config":
        return self.set_termination(
            variation={
                "intervalType": interval_type,
                "value": value,
                "cv": cv,
                "isGlobal": is_global,
            }
        )

    def set_parallelism(self, parallelism: Union[int, Sequence[int], Dict[str, int]]) -> "Config":
        self._data.setdefault("environment", {})["parallelism"] = _normalize_parallelism(parallelism)
        return self

    def set_logging(self, enabled: bool = True, *, prefix: Optional[str] = None) -> "Config":
        logging = {"enabled": enabled}
        if prefix is not None:
            logging["prefix"] = prefix
        self._data.setdefault("environment", {})["logging"] = logging
        return self

    def set_experimental(self, enabled: bool = True) -> "Config":
        self._data.setdefault("environment", {})["isExperimental"] = enabled
        return self

    def set_progress(
        self,
        enabled: bool = True,
        *,
        log_best: Optional[int] = None,
        log_population: Optional[int] = None,
    ) -> "Config":
        progress = {"enabled": enabled}
        if log_best is not None:
            progress["logBest"] = log_best
        if log_population is not None:
            progress["logPopulation"] = log_population
        self._data.setdefault("telemetry", {})["progress"] = progress
        return self

    def set_metrics(self, enabled: bool = True, *, track_population: Optional[int] = None) -> "Config":
        metrics = {"enabled": enabled}
        if track_population is not None:
            metrics["trackPopulation"] = track_population
        self._data.setdefault("telemetry", {})["metrics"] = metrics
        return self

    def include_geojson(self, enabled: bool = True) -> "Config":
        self._data.setdefault("output", {})["includeGeojson"] = enabled
        return self

    def set_evolution(
        self,
        *,
        initial: Optional[Dict[str, Any]] = None,
        population: Optional[Dict[str, Any]] = None,
    ) -> "Config":
        evolution = self._data.setdefault("evolution", {})
        if initial is not None:
            evolution["initial"] = deepcopy(initial)
        if population is not None:
            evolution["population"] = deepcopy(population)
        return self

    def set_initial(
        self,
        method: Dict[str, Any],
        *,
        alternatives: Optional[Sequence[Dict[str, Any]]] = None,
        max_size: int = 4,
        quota: float = 0.05,
    ) -> "Config":
        return self.set_evolution(
            initial={
                "method": deepcopy(method),
                "alternatives": {
                    "methods": deepcopy(list(alternatives or [])),
                    "maxSize": max_size,
                    "quota": quota,
                },
            }
        )

    def set_population_greedy(self, *, selection_size: Optional[int] = None) -> "Config":
        return self.set_evolution(population=Population.greedy(selection_size=selection_size))

    def set_population_elitism(
        self,
        *,
        max_size: Optional[int] = None,
        selection_size: Optional[int] = None,
    ) -> "Config":
        return self.set_evolution(population=Population.elitism(max_size=max_size, selection_size=selection_size))

    def set_population_rosomaxa(
        self,
        *,
        selection_size: Optional[int] = None,
        max_elite_size: Optional[int] = None,
        max_node_size: Optional[int] = None,
        spread_factor: Optional[float] = None,
        distribution_factor: Optional[float] = None,
        rebalance_memory: Optional[int] = None,
        exploration_ratio: Optional[float] = None,
    ) -> "Config":
        return self.set_evolution(
            population=Population.rosomaxa(
                selection_size=selection_size,
                max_elite_size=max_elite_size,
                max_node_size=max_node_size,
                spread_factor=spread_factor,
                distribution_factor=distribution_factor,
                rebalance_memory=rebalance_memory,
                exploration_ratio=exploration_ratio,
            )
        )

    def set_hyper(self, hyper: Dict[str, Any]) -> "Config":
        self._data["hyper"] = deepcopy(hyper)
        return self

    def set_hyper_dynamic(self) -> "Config":
        return self.set_hyper(Hyper.dynamic_selective())

    def set_hyper_static(self, operators: Optional[Sequence[Dict[str, Any]]] = None) -> "Config":
        return self.set_hyper(Hyper.static_selective(operators))


class Recreate:
    """Factory helpers for evolution recreate methods."""

    @staticmethod
    def cheapest(*, weight: int = 1) -> Dict[str, Any]:
        return {"type": "cheapest", "weight": weight}

    @staticmethod
    def farthest(*, weight: int = 1) -> Dict[str, Any]:
        return {"type": "farthest", "weight": weight}

    @staticmethod
    def nearest(*, weight: int = 1) -> Dict[str, Any]:
        return {"type": "nearest", "weight": weight}

    @staticmethod
    def blinks(*, weight: int = 1) -> Dict[str, Any]:
        return {"type": "blinks", "weight": weight}

    @staticmethod
    def skip_random(*, weight: int = 1) -> Dict[str, Any]:
        return {"type": "skip-random", "weight": weight}

    @staticmethod
    def slice(*, weight: int = 1) -> Dict[str, Any]:
        return {"type": "slice", "weight": weight}

    @staticmethod
    def skip_best(start: int, end: int, *, weight: int = 1) -> Dict[str, Any]:
        return {"type": "skip-best", "start": start, "end": end, "weight": weight}

    @staticmethod
    def regret(start: int, end: int, *, weight: int = 1) -> Dict[str, Any]:
        return {"type": "regret", "start": start, "end": end, "weight": weight}

    @staticmethod
    def gaps(min: int, max: int, *, weight: int = 1) -> Dict[str, Any]:
        return {"type": "gaps", "min": min, "max": max, "weight": weight}

    @staticmethod
    def perturbation(probability: float, min: float, max: float, *, weight: int = 1) -> Dict[str, Any]:
        return {"type": "perturbation", "probability": probability, "min": min, "max": max, "weight": weight}


class Population:
    """Factory helpers for evolution population config."""

    @staticmethod
    def greedy(*, selection_size: Optional[int] = None) -> Dict[str, Any]:
        population = {"type": "greedy"}
        _set_if_not_none(population, "selectionSize", selection_size)
        return population

    @staticmethod
    def elitism(*, max_size: Optional[int] = None, selection_size: Optional[int] = None) -> Dict[str, Any]:
        population = {"type": "elitism"}
        _set_if_not_none(population, "maxSize", max_size)
        _set_if_not_none(population, "selectionSize", selection_size)
        return population

    @staticmethod
    def rosomaxa(
        *,
        selection_size: Optional[int] = None,
        max_elite_size: Optional[int] = None,
        max_node_size: Optional[int] = None,
        spread_factor: Optional[float] = None,
        distribution_factor: Optional[float] = None,
        rebalance_memory: Optional[int] = None,
        exploration_ratio: Optional[float] = None,
    ) -> Dict[str, Any]:
        population = {"type": "rosomaxa"}
        _set_if_not_none(population, "selectionSize", selection_size)
        _set_if_not_none(population, "maxEliteSize", max_elite_size)
        _set_if_not_none(population, "maxNodeSize", max_node_size)
        _set_if_not_none(population, "spreadFactor", spread_factor)
        _set_if_not_none(population, "distributionFactor", distribution_factor)
        _set_if_not_none(population, "rebalanceMemory", rebalance_memory)
        _set_if_not_none(population, "explorationRatio", exploration_ratio)
        return population


class Probability:
    """Factory helpers for search operator probabilities."""

    @staticmethod
    def scalar(value: float) -> Dict[str, Any]:
        return {"scalar": value}

    @staticmethod
    def context(
        *,
        jobs: int,
        routes: int,
        phases: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {"threshold": {"jobs": jobs, "routes": routes}, "phases": deepcopy(list(phases))}

    @staticmethod
    def phase(name: str, chance: float) -> Dict[str, Any]:
        return {"type": name, "chance": chance}


class LocalOperator:
    """Factory helpers for local-search operators."""

    @staticmethod
    def swap_star(*, weight: int = 1) -> Dict[str, Any]:
        return {"type": "swap-star", "weight": weight}

    @staticmethod
    def inter_route_best(*, weight: int = 1, noise: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return _operator_with_noise("inter-route-best", weight, noise)

    @staticmethod
    def inter_route_random(*, weight: int = 1, noise: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return _operator_with_noise("inter-route-random", weight, noise)

    @staticmethod
    def intra_route_random(*, weight: int = 1, noise: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return _operator_with_noise("intra-route-random", weight, noise)

    @staticmethod
    def sequence(*, weight: int = 1) -> Dict[str, Any]:
        return {"type": "sequence", "weight": weight}


class Ruin:
    """Factory helpers for ruin methods."""

    @staticmethod
    def adjusted_string(probability: float, lmax: int, cavg: int, alpha: float) -> Dict[str, Any]:
        return {"type": "adjusted-string", "probability": probability, "lmax": lmax, "cavg": cavg, "alpha": alpha}

    @staticmethod
    def neighbour(probability: float, min: int, max: int) -> Dict[str, Any]:
        return {"type": "neighbour", "probability": probability, "min": min, "max": max}

    @staticmethod
    def random_job(probability: float, min: int, max: int) -> Dict[str, Any]:
        return {"type": "random-job", "probability": probability, "min": min, "max": max}

    @staticmethod
    def random_route(probability: float, min: int, max: int) -> Dict[str, Any]:
        return {"type": "random-route", "probability": probability, "min": min, "max": max}

    @staticmethod
    def close_route(probability: float) -> Dict[str, Any]:
        return {"type": "close-route", "probability": probability}

    @staticmethod
    def worst_route(probability: float) -> Dict[str, Any]:
        return {"type": "worst-route", "probability": probability}

    @staticmethod
    def worst_job(probability: float, min: int, max: int, skip: int) -> Dict[str, Any]:
        return {"type": "worst-job", "probability": probability, "min": min, "max": max, "skip": skip}

    @staticmethod
    def cluster(probability: float, min: int, max: int) -> Dict[str, Any]:
        return {"type": "cluster", "probability": probability, "min": min, "max": max}

    @staticmethod
    def group(methods: Sequence[Dict[str, Any]], *, weight: int = 1) -> Dict[str, Any]:
        return {"methods": deepcopy(list(methods)), "weight": weight}


class Hyper:
    """Factory helpers for hyper heuristic configuration."""

    @staticmethod
    def dynamic_selective() -> Dict[str, Any]:
        return {"type": "dynamic-selective"}

    @staticmethod
    def static_selective(operators: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
        hyper = {"type": "static-selective"}
        if operators is not None:
            hyper["operators"] = deepcopy(list(operators))
        return hyper

    @staticmethod
    def decomposition(
        *,
        routes: Dict[str, int],
        repeat: int,
        probability: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {"type": "decomposition", "routes": deepcopy(routes), "repeat": repeat, "probability": deepcopy(probability)}

    @staticmethod
    def local_search(
        *,
        probability: Dict[str, Any],
        times: Dict[str, int],
        operators: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "type": "local-search",
            "probability": deepcopy(probability),
            "times": deepcopy(times),
            "operators": deepcopy(list(operators)),
        }

    @staticmethod
    def ruin_recreate(
        *,
        probability: Dict[str, Any],
        ruins: Sequence[Dict[str, Any]],
        recreates: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "type": "ruin-recreate",
            "probability": deepcopy(probability),
            "ruins": deepcopy(list(ruins)),
            "recreates": deepcopy(list(recreates)),
        }


def noise(probability: float, min: float, max: float) -> Dict[str, Any]:
    return {"probability": probability, "min": min, "max": max}


def min_max(min: int, max: int) -> Dict[str, int]:
    return {"min": min, "max": max}


class InitialSolution(JsonAsset):
    """Initial solution asset."""


class Solution(JsonAsset):
    """Pragmatic solution asset."""

    @property
    def statistic(self) -> Dict[str, Any]:
        data = self.to_dict()
        return data.get("statistic", {}) if isinstance(data, dict) else {}

    @property
    def tours(self) -> List[Dict[str, Any]]:
        data = self.to_dict()
        return data.get("tours", []) if isinstance(data, dict) else []


def solve(
    problem: JsonInput,
    matrices: Optional[Iterable[JsonInput]] = None,
    config: Optional[JsonInput] = None,
    *,
    initial_solution: Optional[JsonInput] = None,
    on_iteration: Optional[IterationCallback] = None,
    every: int = 100,
) -> Solution:
    """Solve a pragmatic problem and return a Solution asset."""

    import vrp_cli

    problem_asset = _ensure_asset(problem, Problem)
    matrix_assets = [_ensure_asset(matrix, RoutingMatrix) for matrix in matrices or []]
    config_asset = _ensure_asset(config or Config(max_generations=3000, max_time=300), Config)
    init_asset = _ensure_asset(initial_solution, InitialSolution) if initial_solution is not None else None

    problem_json = problem_asset.to_json()
    matrices_json = [matrix.to_json() for matrix in matrix_assets]
    config_json = config_asset.to_json()

    if on_iteration is None:
        if init_asset is not None:
            return Solution.from_json(
                vrp_cli.solve_pragmatic_with_init(
                    problem=problem_json,
                    matrices=matrices_json,
                    config=config_json,
                    init_solution=init_asset.to_json(),
                )
            )

        return Solution.from_json(vrp_cli.solve_pragmatic(problem_json, matrices_json, config_json))

    def callback(generation: int, solution_json: str) -> None:
        on_iteration(generation, Solution.from_json(solution_json))

    if init_asset is not None:
        return Solution.from_json(
            vrp_cli.solve_pragmatic_with_init_and_callback(
                problem=problem_json,
                matrices=matrices_json,
                config=config_json,
                init_solution=init_asset.to_json(),
                callback=callback,
                every=every,
            )
        )

    return Solution.from_json(
        vrp_cli.solve_pragmatic_with_callback(
            problem=problem_json,
            matrices=matrices_json,
            config=config_json,
            callback=callback,
            every=every,
        )
    )


def get_locations(problem: JsonInput) -> RoutingLocations:
    return _ensure_asset(problem, Problem).get_locations()


def validate(problem: JsonInput, matrices: Optional[Iterable[JsonInput]] = None) -> None:
    import vrp_cli

    problem_asset = _ensure_asset(problem, Problem)
    matrix_assets = [_ensure_asset(matrix, RoutingMatrix) for matrix in matrices or []]
    vrp_cli.validate_pragmatic(problem_asset.to_json(), [matrix.to_json() for matrix in matrix_assets])


def _ensure_asset(value: JsonInput, cls):
    if isinstance(value, cls):
        return value
    return cls.from_json(value)


def _task(
    location: Any,
    demand: Sequence[int],
    *,
    duration: Union[int, float],
    times: Optional[Sequence[Sequence[str]]],
    tag: Optional[str],
) -> Dict[str, Any]:
    place = {
        "location": _location(location),
        "duration": duration,
    }
    if times is not None:
        place["times"] = [list(window) for window in times]
    if tag is not None:
        place["tag"] = tag

    return {"places": [place], "demand": list(demand)}


def _location(location: Any) -> Dict[str, Any]:
    if isinstance(location, dict):
        return deepcopy(location)

    if isinstance(location, (list, tuple)) and len(location) == 2:
        return {"lat": location[0], "lng": location[1]}

    if hasattr(location, "lat") and hasattr(location, "lng"):
        return {"lat": location.lat, "lng": location.lng}

    raise ValueError("location must be a dict, a (lat, lng) pair, or an object with lat/lng attributes")


def _read_json(source: JsonInput) -> JsonData:
    if isinstance(source, JsonAsset):
        return source.to_dict()

    if isinstance(source, (dict, list)):
        return deepcopy(source)

    if not isinstance(source, (str, Path)):
        return _to_jsonable(source)

    path = Path(source)
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        pass

    return json.loads(str(source))


def _to_jsonable(value: Any) -> JsonData:
    if hasattr(value, "to_dict"):
        return value.to_dict()

    if pydantic_encoder is not None:
        return json.loads(json.dumps(value, default=pydantic_encoder))

    return json.loads(json.dumps(value, default=_json_default))


def _json_default(value: Any) -> Any:
    if pydantic_encoder is not None:
        return pydantic_encoder(value)

    if hasattr(value, "isoformat"):
        return value.isoformat()

    if hasattr(value, "__dict__"):
        return value.__dict__

    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _set_if_not_none(target: Dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        target[key] = value


def _operator_with_noise(name: str, weight: int, noise: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    operator = {"type": name, "weight": weight}
    if noise is not None:
        operator["noise"] = deepcopy(noise)
    return operator


def _normalize_parallelism(parallelism: Union[int, Sequence[int], Dict[str, int]]) -> Dict[str, int]:
    if isinstance(parallelism, int):
        return {"numThreadPools": parallelism, "threadsPerPool": 1}

    if isinstance(parallelism, (list, tuple)) and len(parallelism) == 2:
        return {"numThreadPools": int(parallelism[0]), "threadsPerPool": int(parallelism[1])}

    return dict(parallelism)
