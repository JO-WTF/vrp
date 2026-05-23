from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, Generator, Iterable, Iterator, List, Optional, Sequence, Union

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
        from . import _vrp_cli as vrp_cli

        return RoutingLocations.from_json(vrp_cli.get_routing_locations(self.to_json()))

    def validate(self, matrices: Optional[Iterable[JsonInput]] = None) -> None:
        """Run native validation on the problem and optionally matrices."""
        from . import validate

        validate(self, matrices)

    def validate_dimensions(self) -> None:
        """Validate that all capacities and demands have consistent multi-dimensional lengths."""
        dim = None

        for v in self._vehicles():
            cap = v.get("capacity")
            if cap is not None:
                if dim is None:
                    dim = len(cap)
                elif len(cap) != dim:
                    raise ValueError(f"Vehicle type '{v.get('typeId')}' capacity dimension {len(cap)} mismatches expected {dim}")

        for job in self._jobs():
            for task_type in ["pickups", "deliveries", "replacements", "services"]:
                for task in job.get(task_type, []):
                    dem = task.get("demand")
                    if dem is not None:
                        if dim is None:
                            dim = len(dem)
                        elif len(dem) != dim:
                            raise ValueError(f"Job '{job.get('id')}' demand dimension {len(dem)} mismatches expected {dim}")

    def validate_problem(self) -> None:
        """Run basic Python-level validations on the problem before calling native bindings."""
        self.validate_dimensions()
        # Ensure we have at least one vehicle and one job
        if not self._vehicles():
            raise ValueError("Problem must have at least one vehicle.")
        if not self._jobs():
            raise ValueError("Problem must have at least one job.")

    def add_delivery(
        self,
        job_id: str,
        location: Any,
        demand: Sequence[int],
        *,
        duration: Union[int, float] = 0,
        times: Optional[Sequence[Sequence[str]]] = None,
        tag: Optional[str] = None,
        order: Optional[int] = None,
        **extra: Any,
    ) -> "Problem":
        return self._add_job_task(job_id, "deliveries", location, demand, duration=duration, times=times, tag=tag, order=order, **extra)

    def add_pickup(
        self,
        job_id: str,
        location: Any,
        demand: Sequence[int],
        *,
        duration: Union[int, float] = 0,
        times: Optional[Sequence[Sequence[str]]] = None,
        tag: Optional[str] = None,
        order: Optional[int] = None,
        **extra: Any,
    ) -> "Problem":
        return self._add_job_task(job_id, "pickups", location, demand, duration=duration, times=times, tag=tag, order=order, **extra)

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
        pickup_order: Optional[int] = None,
        delivery_order: Optional[int] = None,
        **extra: Any,
    ) -> "Problem":
        pickup_task = _task(pickup_location, demand, duration=pickup_duration, times=pickup_times, tag=pickup_tag)
        if pickup_order is not None:
            pickup_task["order"] = pickup_order
        delivery_task = _task(delivery_location, demand, duration=delivery_duration, times=delivery_times, tag=delivery_tag)
        if delivery_order is not None:
            delivery_task["order"] = delivery_order

        job = {
            "id": job_id,
            "pickups": [pickup_task],
            "deliveries": [delivery_task],
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

    def add_service(
        self,
        job_id: str,
        location: Any,
        *,
        duration: Union[int, float] = 0,
        times: Optional[Sequence[Sequence[str]]] = None,
        tag: Optional[str] = None,
        **extra: Any,
    ) -> "Problem":
        """Add a service job (no demand, just a visit with optional duration/time-window)."""
        place: Dict[str, Any] = {"location": _location(location), "duration": duration}
        if times is not None:
            place["times"] = [list(w) for w in times]
        if tag is not None:
            place["tag"] = tag
        job: Dict[str, Any] = {"id": job_id, "services": [{"places": [place]}]}
        job.update(extra)
        self._jobs().append(job)
        return self

    def set_job_skills(
        self,
        job_id: str,
        *,
        all_of: Optional[Sequence[str]] = None,
        one_of: Optional[Sequence[str]] = None,
        none_of: Optional[Sequence[str]] = None,
    ) -> "Problem":
        """Attach skill requirements to an already-added job."""
        skills: Dict[str, Any] = {}
        if all_of is not None:
            skills["allOf"] = list(all_of)
        if one_of is not None:
            skills["oneOf"] = list(one_of)
        if none_of is not None:
            skills["noneOf"] = list(none_of)
        self._find_job(job_id)["skills"] = skills
        return self

    def set_job_priority(self, job_id: str, priority: int) -> "Problem":
        """Set the dispatch priority of an already-added job (1 = highest)."""
        self._find_job(job_id)["priority"] = priority
        return self

    def set_job_value(self, job_id: str, value: float) -> "Problem":
        """Set the value of an already-added job (used with maximize-value objective)."""
        self._find_job(job_id)["value"] = value
        return self

    def set_job_group(self, job_id: str, group: str) -> "Problem":
        """Set the job group. Jobs in the same group are assigned to the same tour or unassigned together."""
        self._find_job(job_id)["group"] = group
        return self

    def set_job_compatibility(self, job_id: str, compatibility: str) -> "Problem":
        """Set the compatibility group. Jobs with different compatibility cannot be in the same tour."""
        self._find_job(job_id)["compatibility"] = compatibility
        return self

    def add_vehicle_recharge(
        self,
        vehicle_type_id: str,
        max_distance: Union[int, float],
        stations: Sequence[Dict[str, Any]],
        shift_index: int = 0,
    ) -> "Problem":
        """Add recharge stations to a vehicle's shift."""
        vehicle = self._find_vehicle(vehicle_type_id)
        shift = vehicle["shifts"][shift_index]
        shift["recharges"] = {
            "maxDistance": max_distance,
            "stations": list(stations),
        }
        return self

    def add_vehicle_reload_resource(
        self,
        resource_id: str,
        capacity: Sequence[int],
    ) -> "Problem":
        """Add a shared reload resource to the fleet."""
        resources = self._data.setdefault("fleet", {}).setdefault("resources", [])
        resources.append({"type": "reload", "id": resource_id, "capacity": list(capacity)})
        return self

    def add_multi_place_task(
        self,
        job_id: str,
        task_type: str,
        places: Sequence[Dict[str, Any]],
        demand: Sequence[int],
        *,
        order: Optional[int] = None,
        **extra: Any,
    ) -> "Problem":
        """Add a job with a task that has multiple alternative places."""
        task: Dict[str, Any] = {"places": list(places), "demand": list(demand)}
        if order is not None:
            task["order"] = order
        job = {"id": job_id, task_type: [task]}
        job.update(extra)
        self._jobs().append(job)
        return self

    def add_vehicle_shift(
        self,
        vehicle_type_id: str,
        start_location: Any,
        start_earliest: str,
        end_location: Optional[Any] = None,
        end_latest: Optional[str] = None,
    ) -> "Problem":
        """Add an additional shift to an existing vehicle type."""
        vehicle = self._find_vehicle(vehicle_type_id)
        shift: Dict[str, Any] = {
            "start": {
                "earliest": start_earliest,
                "location": _location(start_location),
            },
        }
        if end_location is not None or end_latest is not None:
            shift["end"] = {
                "latest": end_latest or start_earliest,
                "location": _location(end_location or start_location),
            }
        vehicle["shifts"].append(shift)
        return self

    def set_vehicle_open_end(self, vehicle_type_id: str, shift_index: int = 0) -> "Problem":
        """Remove the end location from a vehicle's shift, making it an open route."""
        vehicle = self._find_vehicle(vehicle_type_id)
        shift = vehicle["shifts"][shift_index]
        shift.pop("end", None)
        return self

    def set_vehicle_dispatch(self, vehicle_type_id: str, latest: str, shift_index: int = 0) -> "Problem":
        """Limit departure time optimization by setting a latest start time."""
        vehicle = self._find_vehicle(vehicle_type_id)
        shift = vehicle["shifts"][shift_index]
        shift["start"]["latest"] = latest
        return self

    def set_profile_scale(self, vehicle_type_id: str, scale: float) -> "Problem":
        """Set the duration scale factor for a vehicle type's profile."""
        vehicle = self._find_vehicle(vehicle_type_id)
        vehicle["profile"]["scale"] = scale
        return self

    def set_matrix_profile_speed(self, profile_name: str, speed: float) -> "Problem":
        """Set the approximation speed (m/s) for a matrix profile (used when matrix is omitted)."""
        for profile in self._profiles():
            if profile.get("name") == profile_name:
                profile["speed"] = speed
                return self
        raise KeyError(f"Matrix profile '{profile_name}' not found.")

    def add_vehicle_break(
        self,
        vehicle_type_id: str,
        *,
        times: Sequence[Sequence[str]],
        duration: Union[int, float],
        locations: Optional[Sequence[Any]] = None,
        shift_index: int = 0,
    ) -> "Problem":
        """Add a time-window break to a vehicle type's shift.

        ``times`` is a list of ``[earliest, latest]`` time-window pairs.
        ``locations`` is an optional list of allowed break locations; if omitted
        the break can happen anywhere on the route.
        """
        vehicle = self._find_vehicle(vehicle_type_id)
        shift = vehicle["shifts"][shift_index]
        brk: Dict[str, Any] = {
            "time": {"times": [list(w) for w in times]},
            "duration": duration,
        }
        if locations is not None:
            brk["places"] = [{"location": _location(loc), "duration": duration} for loc in locations]
        shift.setdefault("breaks", []).append(brk)
        return self

    def add_vehicle_reload(
        self,
        vehicle_type_id: str,
        location: Any,
        *,
        duration: Union[int, float] = 0,
        times: Optional[Sequence[Sequence[str]]] = None,
        tag: Optional[str] = None,
        shift_index: int = 0,
    ) -> "Problem":
        """Add a reload stop to a vehicle type's shift (allows refilling capacity mid-route)."""
        vehicle = self._find_vehicle(vehicle_type_id)
        shift = vehicle["shifts"][shift_index]
        reload: Dict[str, Any] = {"location": _location(location), "duration": duration}
        if times is not None:
            reload["times"] = [list(w) for w in times]
        if tag is not None:
            reload["tag"] = tag
        shift.setdefault("reloads", []).append(reload)
        return self

    def set_vehicle_limits(
        self,
        vehicle_type_id: str,
        *,
        max_distance: Optional[Union[int, float]] = None,
        max_duration: Optional[Union[int, float]] = None,
        tour_size: Optional[int] = None,
    ) -> "Problem":
        """Set travel / tour-size limits for a vehicle type."""
        vehicle = self._find_vehicle(vehicle_type_id)
        limits: Dict[str, Any] = {}
        if max_distance is not None:
            limits["maxDistance"] = max_distance
        if max_duration is not None:
            limits["shiftTime"] = max_duration
        if tour_size is not None:
            limits["tourSize"] = tour_size
        if limits:
            vehicle["limits"] = limits
        return self

    def set_vehicle_skills(self, vehicle_type_id: str, skills: Sequence[str]) -> "Problem":
        """Assign a list of skills to a vehicle type."""
        self._find_vehicle(vehicle_type_id)["skills"] = list(skills)
        return self

    def add_profile(self, name: str, **extra: Any) -> "Problem":
        profiles = self._profiles()
        if not any(profile.get("name") == name for profile in profiles):
            profile = {"name": name}
            profile.update(extra)
            profiles.append(profile)
        return self

    # ------------------------------------------------------------------
    # Typed relation helpers
    # ------------------------------------------------------------------

    def add_relation(self, relation_type: str, jobs: Sequence[str], vehicle_id: str, **extra: Any) -> "Problem":
        """Add a raw relation (use typed helpers below when possible)."""
        relation = {"type": relation_type, "jobs": list(jobs), "vehicleId": vehicle_id}
        relation.update(extra)
        self._data.setdefault("plan", {}).setdefault("relations", []).append(relation)
        return self

    def add_relation_sequence(self, jobs: Sequence[str], vehicle_id: str) -> "Problem":
        """Enforce that *jobs* are served in the given order (but not necessarily consecutively)."""
        return self.add_relation("sequence", jobs, vehicle_id)

    def add_relation_strict(
        self, jobs: Sequence[str], vehicle_id: str, shift_index: Optional[int] = None
    ) -> "Problem":
        """Enforce that *jobs* are served in strict consecutive order on *vehicle_id*."""
        extra: Dict[str, Any] = {}
        if shift_index is not None:
            extra["shiftIndex"] = shift_index
        return self.add_relation("strict", jobs, vehicle_id, **extra)

    def add_relation_tour(self, jobs: Sequence[str], vehicle_id: str) -> "Problem":
        """Assign *jobs* exclusively to *vehicle_id* (any order)."""
        return self.add_relation("tour", jobs, vehicle_id)

    # ------------------------------------------------------------------
    # Typed objective helpers
    # ------------------------------------------------------------------

    def set_objectives(self, objectives: Sequence[Sequence[Dict[str, Any]]]) -> "Problem":
        """Set raw objectives (list-of-lists of dicts). Use Objective helpers for typed access."""
        self._data["objectives"] = deepcopy(objectives)
        return self

    def set_objectives_typed(self, objectives: Sequence[Sequence["Objective"]]) -> "Problem":
        """Set objectives using :class:`Objective` typed helpers.

        Each inner list is one priority level; earlier lists take priority.
        """
        self._data["objectives"] = [[obj.to_dict() for obj in group] for group in objectives]
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
        order: Optional[int] = None,
        **extra: Any,
    ) -> "Problem":
        task = _task(location, demand, duration=duration, times=times, tag=tag)
        if order is not None:
            task["order"] = order
        job = {"id": job_id, task_type: [task]}
        job.update(extra)
        self._jobs().append(job)
        return self

    def _jobs(self) -> List[Dict[str, Any]]:
        return self._data.setdefault("plan", {}).setdefault("jobs", [])

    def _vehicles(self) -> List[Dict[str, Any]]:
        return self._data.setdefault("fleet", {}).setdefault("vehicles", [])

    def _profiles(self) -> List[Dict[str, Any]]:
        return self._data.setdefault("fleet", {}).setdefault("profiles", [])

    def validate_matrices(self, matrices: Sequence["RoutingMatrix"]) -> None:
        """Validate matrices against the problem's profiles and location dimensions."""
        if not matrices:
            return

        defined_profiles = {p.get("name") for p in self._profiles() if "name" in p}
        
        expected_size = None
        try:
            locations = self.get_locations()
            num_locations = len(locations)
            expected_size = num_locations * num_locations
        except Exception:
            pass

        for idx, matrix in enumerate(matrices):
            m_dict = matrix.to_dict()
            profile = m_dict.get("profile")
            if profile and profile not in defined_profiles:
                raise ValueError(
                    f"Matrix at index {idx} specifies profile '{profile}', "
                    f"but it is not defined in the problem. Defined profiles: {defined_profiles}"
                )
            
            if expected_size is not None:
                for field in ["travelTimes", "distances"]:
                    data = m_dict.get(field)
                    if data is not None and len(data) != expected_size:
                        raise ValueError(
                            f"Matrix at index {idx} has '{field}' of length {len(data)}, "
                            f"but problem has {num_locations} unique locations (expected size {expected_size})"
                        )

    def _find_job(self, job_id: str) -> Dict[str, Any]:
        for job in self._jobs():
            if job.get("id") == job_id:
                return job
        raise KeyError(f"Job '{job_id}' not found in problem.")

    def _find_vehicle(self, type_id: str) -> Dict[str, Any]:
        for vehicle in self._vehicles():
            if vehicle.get("typeId") == type_id:
                return vehicle
        raise KeyError(f"Vehicle type '{type_id}' not found in problem.")


class Objective:
    """Typed helper for a single pragmatic objective entry."""

    def __init__(self, type: str, **options: Any) -> None:
        self._type = type
        self._options = options

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"type": self._type}
        if self._options:
            d.update(self._options)
        return d

    # -- Named constructors -------------------------------------------

    @staticmethod
    def minimize_cost() -> "Objective":
        return Objective("minimize-cost")

    @staticmethod
    def minimize_unassigned(breaks: Optional[float] = None) -> "Objective":
        opts: Dict[str, Any] = {}
        if breaks is not None:
            opts["breaks"] = breaks
        return Objective("minimize-unassigned", **opts)

    @staticmethod
    def minimize_tours() -> "Objective":
        return Objective("minimize-tours")

    @staticmethod
    def maximize_tours() -> "Objective":
        return Objective("maximize-tours")

    @staticmethod
    def maximize_value() -> "Objective":
        return Objective("maximize-value")

    @staticmethod
    def minimize_distance() -> "Objective":
        return Objective("minimize-distance")

    @staticmethod
    def minimize_duration() -> "Objective":
        return Objective("minimize-duration")

    @staticmethod
    def minimize_arrival_time() -> "Objective":
        return Objective("minimize-arrival-time")

    @staticmethod
    def balance_max_load(threshold: Optional[float] = None) -> "Objective":
        opts: Dict[str, Any] = {}
        if threshold is not None:
            opts["options"] = {"threshold": threshold}
        return Objective("balance-max-load", **opts)

    @staticmethod
    def balance_activities(threshold: Optional[float] = None) -> "Objective":
        opts: Dict[str, Any] = {}
        if threshold is not None:
            opts["options"] = {"threshold": threshold}
        return Objective("balance-activities", **opts)

    @staticmethod
    def balance_distance(threshold: Optional[float] = None) -> "Objective":
        opts: Dict[str, Any] = {}
        if threshold is not None:
            opts["options"] = {"threshold": threshold}
        return Objective("balance-distance", **opts)

    @staticmethod
    def balance_duration(threshold: Optional[float] = None) -> "Objective":
        opts: Dict[str, Any] = {}
        if threshold is not None:
            opts["options"] = {"threshold": threshold}
        return Objective("balance-duration", **opts)

    def __repr__(self) -> str:
        return f"Objective({self._type!r})"


class RoutingLocations(JsonAsset):
    """Ordered unique locations used to request routing matrices."""

    def __len__(self) -> int:
        return len(self._data) if isinstance(self._data, list) else 0

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        if isinstance(self._data, list):
            yield from self._data


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

    @classmethod
    def from_2d(
        cls,
        durations: Sequence[Sequence[Union[int, float]]],
        distances: Sequence[Sequence[Union[int, float]]],
        *,
        profile: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> "RoutingMatrix":
        """Build a :class:`RoutingMatrix` from 2-D duration and distance arrays.

        Both arrays must be square matrices of the same dimension *n × n*,
        where *n* is the number of routing locations.  The values are flattened
        in row-major order, matching the pragmatic format expectation.

        Example::

            matrix = RoutingMatrix.from_2d(
                durations=[[0, 60, 90], [60, 0, 30], [90, 30, 0]],
                distances=[[0, 1000, 1500], [1000, 0, 500], [1500, 500, 0]],
                profile="car",
            )
        """
        flat_d = [v for row in durations for v in row]
        flat_m = [v for row in distances for v in row]
        n = len(durations)
        if len(flat_d) != n * n or len(flat_m) != n * n:
            raise ValueError(
                f"from_2d: durations and distances must both be {n}×{n} square matrices"
            )
        return cls(durations=flat_d, distances=flat_m, profile=profile, timestamp=timestamp)


class MatrixCollection:
    """A helper that groups :class:`RoutingMatrix` objects by profile.

    Use :meth:`add` to register matrices (one per profile / timestamp),
    then pass :meth:`to_list` to :func:`solve` as the ``matrices`` argument.

    Example::

        col = MatrixCollection()
        col.add(RoutingMatrix(profile="car", durations=[...], distances=[...]))
        col.add(RoutingMatrix(profile="bike", durations=[...], distances=[...]))
        solution = solve(problem, matrices=col.to_list(), config=config)
    """

    def __init__(self) -> None:
        self._matrices: List[RoutingMatrix] = []

    def add(self, matrix: RoutingMatrix) -> "MatrixCollection":
        """Register a matrix and return *self* for chaining."""
        self._matrices.append(matrix)
        return self

    def add_time_dependent(
        self,
        profile: str,
        timestamp_to_data: Dict[str, Dict[str, Sequence[Union[int, float]]]],
    ) -> "MatrixCollection":
        """Register multiple matrices for the same profile across different timestamps.
        
        The dictionary maps RFC3339 timestamps to dictionaries containing 
        ``durations`` and ``distances`` sequences.
        """
        for timestamp, data in timestamp_to_data.items():
            self._matrices.append(
                RoutingMatrix(
                    profile=profile,
                    timestamp=timestamp,
                    durations=data.get("durations"),
                    distances=data.get("distances"),
                )
            )
        return self

    def to_list(self) -> List[RoutingMatrix]:
        """Return a plain list suitable for the ``matrices`` argument of :func:`solve`."""
        return list(self._matrices)

    def __len__(self) -> int:
        return len(self._matrices)

    def __iter__(self) -> Iterator[RoutingMatrix]:
        return iter(self._matrices)


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
    def defaults(
        cls,
        max_time: Optional[int] = None,
        max_generations: Optional[int] = None,
        variation: Optional[int] = None,
    ) -> "Config":
        """Create a default configuration with optional termination limits."""
        data: Dict[str, Any] = {}
        if max_time is not None or max_generations is not None or variation is not None:
            term: Dict[str, Any] = {}
            if max_time is not None:
                term["maxTime"] = max_time
            if max_generations is not None:
                term["maxGenerations"] = max_generations
            if variation is not None:
                term["variation"] = {"intervalType": "sample", "amount": variation, "tolerance": 0.1}
            data["termination"] = term
        return cls(data)

    @classmethod
    def fast(cls) -> "Config":
        """Create a configuration optimized for fast heuristic execution.
        
        Uses greedy population and limits max generations to a small number.
        """
        return cls.defaults(max_generations=100).set_population_greedy(selection_size=2)

    @classmethod
    def deep(cls) -> "Config":
        """Create a configuration optimized for deep, high-quality search.
        
        Uses the rosomaxa population and allows more generations.
        """
        return cls.defaults(max_generations=3000).set_population_rosomaxa()

    @classmethod
    def large_scale(cls) -> "Config":
        """Create a configuration optimized for large scale problems."""
        return cls.defaults(max_generations=500).set_population_rosomaxa().set_hyper_static()

    def merge(self, other: "Config") -> "Config":
        """Merge another Config into this one, overwriting existing fields."""
        def dict_merge(dct: Dict[str, Any], merge_dct: Dict[str, Any]) -> None:
            for k, v in merge_dct.items():
                if k in dct and isinstance(dct[k], dict) and isinstance(v, dict):
                    dict_merge(dct[k], v)
                else:
                    from copy import deepcopy
                    dct[k] = deepcopy(v)

        dict_merge(self._data, other.to_dict())
        return self

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

    def validate(self) -> None:
        """Validate config parameters before solving."""
        term = self._data.get("termination", {})
        if "maxTime" in term and term["maxTime"] <= 0:
            raise ValueError("maxTime must be greater than 0")
        if "maxGenerations" in term and term["maxGenerations"] <= 0:
            raise ValueError("maxGenerations must be greater than 0")

        evo = self._data.get("evolution", {})
        pop = evo.get("population", {})
        if pop.get("type") in ["elitism", "rosomaxa"]:
            if pop.get("maxSize") is not None and pop["maxSize"] <= 0:
                raise ValueError("population maxSize must be greater than 0")
            if pop.get("selectionSize") is not None and pop["selectionSize"] <= 0:
                raise ValueError("population selectionSize must be greater than 0")

        # Initial methods
        initial = evo.get("initial", {})
        methods = []
        if "method" in initial:
            methods.append(initial["method"])
        methods.extend(initial.get("alternatives", {}).get("methods", []))
        for method in methods:
            if method and "weight" in method and method["weight"] <= 0:
                raise ValueError(f"Initial method weight must be > 0, got {method['weight']}")

        # Hyper methods
        hyper = self._data.get("hyper", {})
        if hyper.get("type") in ("static-selective", "dynamic-selective"):
            for op in hyper.get("operators", []):
                if "operators" in op:
                    for sub_op in op["operators"]:
                        if "weight" in sub_op and sub_op["weight"] <= 0:
                            raise ValueError(f"Hyper operator weight must be > 0, got {sub_op['weight']}")


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
    def worst_job(probability: float, min: int, max: int, skip: int = 0) -> Dict[str, Any]:
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

    def __init__(self, data: Optional[JsonData] = None):
        if data is None:
            data = {"statistic": self._dummy_statistic(), "tours": [], "unassigned": []}
        super().__init__(data)

    @classmethod
    def from_json(cls, source: JsonInput) -> "InitialSolution":
        return cls(_read_json(source))

    @classmethod
    def from_dict(cls, data: JsonData) -> "InitialSolution":
        return cls(data)

    def add_tour(
        self,
        vehicle_id: str,
        type_id: str,
        stops: Sequence[Dict[str, Any]],
        shift_index: int = 0,
    ) -> "InitialSolution":
        """Add a tour to the initial solution.
        
        A tour requires stops. You can use :meth:`create_stop` to build them.
        """
        tour = {
            "vehicleId": vehicle_id,
            "typeId": type_id,
            "shiftIndex": shift_index,
            "statistic": self._dummy_statistic(),
            "stops": list(stops),
        }
        self._data.setdefault("tours", []).append(tour)
        return self

    def add_unassigned(
        self,
        job_id: str,
        code: str,
        description: str,
    ) -> "InitialSolution":
        """Add a job to the unassigned list."""
        unassigned = {
            "jobId": job_id,
            "reasons": [{"code": code, "description": description}],
        }
        self._data.setdefault("unassigned", []).append(unassigned)
        return self

    @staticmethod
    def create_stop(
        location: Any,
        activities: Sequence[Dict[str, Any]],
        time: Optional[Sequence[str]] = None,
        load: Optional[Sequence[int]] = None,
        distance: int = 0,
    ) -> Dict[str, Any]:
        """Helper to create a stop dictionary for an initial solution.
        
        Dummy values are provided for time, load, and distance if not specified.
        """
        from . import _location

        arrival = time[0] if time else "1970-01-01T00:00:00Z"
        departure = time[1] if time and len(time) > 1 else arrival
        
        return {
            "location": _location(location),
            "time": {"arrival": arrival, "departure": departure},
            "distance": distance,
            "load": list(load) if load is not None else [0],
            "activities": list(activities),
        }

    @staticmethod
    def create_activity(job_id: str, activity_type: str, **kwargs: Any) -> Dict[str, Any]:
        """Helper to create an activity dictionary.
        
        Types can be 'pickup', 'delivery', 'service', 'departure', 'arrival', 'break', 'reload', 'recharge'.
        """
        activity = {"jobId": job_id, "type": activity_type}
        activity.update(kwargs)
        return activity

    @staticmethod
    def _dummy_statistic() -> Dict[str, Any]:
        return {
            "cost": 0,
            "distance": 0,
            "duration": 0,
            "times": {
                "driving": 0,
                "serving": 0,
                "waiting": 0,
                "break": 0,
                "commuting": 0,
                "parking": 0,
            },
        }


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

    @property
    def unassigned(self) -> List[Dict[str, Any]]:
        """Return the list of unassigned jobs (empty list if all jobs were assigned)."""
        data = self.to_dict()
        return data.get("unassigned", []) if isinstance(data, dict) else []

    @property
    def geojson(self) -> Optional[Dict[str, Any]]:
        """GeoJSON FeatureCollection if ``output.includeGeojson`` was requested, else ``None``."""
        data = self.to_dict()
        if not isinstance(data, dict):
            return None
        extras = data.get("extras", {})
        return extras.get("features") if isinstance(extras, dict) else None

    @property
    def total_cost(self) -> float:
        """Total solution cost as reported in the top-level statistic."""
        return float(self.statistic.get("cost", 0.0))

    @property
    def total_distance(self) -> int:
        """Total travel distance (in matrix units) across all tours."""
        return int(self.statistic.get("distance", 0))

    @property
    def total_duration(self) -> int:
        """Total elapsed duration (in seconds) across all tours."""
        return int(self.statistic.get("duration", 0))

    def iter_tours(self) -> "Generator[TourView, None, None]":
        """Iterate over all tours as :class:`TourView` objects."""
        for tour_dict in self.tours:
            yield TourView(tour_dict)

    def summary(self) -> str:
        """Return a human-readable summary of the solution."""
        stat = self.statistic
        tours = self.tours
        unassigned = self.unassigned
        times = stat.get("times", {})
        lines = [
            f"Solution summary:",
            f"  Tours        : {len(tours)}",
            f"  Unassigned   : {len(unassigned)}",
            f"  Cost         : {stat.get('cost', 0):.2f}",
            f"  Distance     : {stat.get('distance', 0)}",
            f"  Duration     : {stat.get('duration', 0)}s",
        ]
        if times:
            lines += [
                f"    Driving    : {times.get('driving', 0)}s",
                f"    Serving    : {times.get('serving', 0)}s",
                f"    Waiting    : {times.get('waiting', 0)}s",
            ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"Solution(tours={len(self.tours)}, unassigned={len(self.unassigned)}, "
            f"cost={self.total_cost:.2f})"
        )


class TourView:
    """A read-only view of a single tour in a :class:`Solution`.

    Wraps the raw tour dict returned by the solver and exposes
    structured accessors without copying the underlying data.
    """

    __slots__ = ("_data",)

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data = data

    @property
    def vehicle_id(self) -> str:
        """The full vehicle ID (e.g. ``'vehicle_1_1'``)."""
        return self._data.get("vehicleId", "")

    @property
    def type_id(self) -> str:
        """The vehicle type ID."""
        return self._data.get("typeId", "")

    @property
    def shift_index(self) -> int:
        return int(self._data.get("shiftIndex", 0))

    @property
    def stops(self) -> List[Dict[str, Any]]:
        """Raw stop list for this tour."""
        return self._data.get("stops", [])

    @property
    def statistic(self) -> Dict[str, Any]:
        """Per-tour statistic dict."""
        return self._data.get("statistic", {})

    @property
    def cost(self) -> float:
        return float(self.statistic.get("cost", 0.0))

    @property
    def distance(self) -> int:
        return int(self.statistic.get("distance", 0))

    @property
    def duration(self) -> int:
        return int(self.statistic.get("duration", 0))

    def iter_stops(self) -> "Generator[StopView, None, None]":
        """Iterate over the stops of this tour as :class:`StopView` objects."""
        for stop_dict in self.stops:
            yield StopView(stop_dict)

    def to_dict(self) -> Dict[str, Any]:
        return deepcopy(self._data)

    def __repr__(self) -> str:
        return f"TourView(vehicle_id={self.vehicle_id!r}, stops={len(self.stops)})"


class StopView:
    """A read-only view of a single stop inside a :class:`TourView`."""

    __slots__ = ("_data",)

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data = data

    @property
    def location(self) -> Dict[str, float]:
        """``{"lat": ..., "lng": ...}`` dict for this stop."""
        return self._data.get("location", {})

    @property
    def lat(self) -> float:
        return float(self.location.get("lat", 0.0))

    @property
    def lng(self) -> float:
        return float(self.location.get("lng", 0.0))

    @property
    def arrival(self) -> str:
        return self._data.get("time", {}).get("arrival", "")

    @property
    def departure(self) -> str:
        return self._data.get("time", {}).get("departure", "")

    @property
    def distance(self) -> int:
        return int(self._data.get("distance", 0))

    @property
    def load(self) -> List[int]:
        return list(self._data.get("load", []))

    @property
    def activities(self) -> List[Dict[str, Any]]:
        """Raw activities list for this stop."""
        return self._data.get("activities", [])

    def job_ids(self) -> List[str]:
        """Return the job IDs of all activities at this stop."""
        return [act.get("jobId", "") for act in self.activities]

    def to_dict(self) -> Dict[str, Any]:
        return deepcopy(self._data)

    def __repr__(self) -> str:
        return f"StopView(lat={self.lat}, lng={self.lng}, activities={len(self.activities)})"


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

    from . import _vrp_cli as vrp_cli

    problem_asset = _ensure_asset(problem, Problem)
    matrix_assets = [_ensure_asset(matrix, RoutingMatrix) for matrix in matrices or []]
    config_asset = _ensure_asset(config or Config(max_generations=3000, max_time=300), Config)
    init_asset = _ensure_asset(initial_solution, InitialSolution) if initial_solution is not None else None

    problem_asset.validate_problem()
    config_asset.validate()
    if matrix_assets:
        problem_asset.validate_matrices(matrix_assets)

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


def convert_to_pragmatic(input_format: str, inputs: Sequence[str]) -> Problem:
    """Convert an external routing problem format into a pragmatic Problem.

    Parameters
    ----------
    input_format:
        The format identifier (e.g., "tsplib", "cvrp").
    inputs:
        A sequence of raw string contents representing the input files.

    Returns
    -------
    Problem
        The converted pragmatic problem.

    Raises
    ------
    OSError
        If the conversion fails.
    """
    from . import _vrp_cli as vrp_cli

    raw = vrp_cli.convert_to_pragmatic(input_format, list(inputs))
    return Problem.from_json(raw)


def validate(problem: JsonInput, matrices: Optional[Iterable[JsonInput]] = None) -> None:
    from . import _vrp_cli as vrp_cli

    problem_asset = _ensure_asset(problem, Problem)
    matrix_assets = [_ensure_asset(matrix, RoutingMatrix) for matrix in matrices or []]
    vrp_cli.validate_pragmatic(problem_asset.to_json(), [matrix.to_json() for matrix in matrix_assets])

class CheckResult:
    """Result of a solution feasibility check.

    Attributes
    ----------
    violations : List[str]
        Human-readable descriptions of every constraint violation found in the
        solution.  An empty list means the solution is fully feasible.

    Examples
    --------
    ::

        result = check(problem, solution, matrices)
        if result.is_feasible:
            print("Solution is valid!")
        else:
            for msg in result.violations:
                print(f"  VIOLATION: {msg}")

        # Or raise immediately on infeasibility:
        result.raise_if_infeasible()
    """

    def __init__(self, violations: List[str]) -> None:
        self.violations: List[str] = violations

    @property
    def is_feasible(self) -> bool:
        """``True`` when no constraint violations were found."""
        return len(self.violations) == 0

    def raise_if_infeasible(self) -> None:
        """Raise :class:`ValueError` if the solution has constraint violations.

        The exception message contains all violation descriptions joined by
        newlines so they are easy to read in tracebacks.
        """
        if not self.is_feasible:
            detail = "\n".join(f"  - {v}" for v in self.violations)
            raise ValueError(
                f"Solution is infeasible ({len(self.violations)} violation(s)):\n{detail}"
            )

    def __bool__(self) -> bool:
        return self.is_feasible

    def __len__(self) -> int:
        return len(self.violations)

    def __iter__(self) -> Iterator[str]:
        return iter(self.violations)

    def __repr__(self) -> str:
        if self.is_feasible:
            return "CheckResult(feasible)"
        return f"CheckResult(infeasible, violations={len(self.violations)})"

    def __str__(self) -> str:
        if self.is_feasible:
            return "Solution is feasible."
        lines = [f"Solution is infeasible ({len(self.violations)} violation(s)):"]
        for v in self.violations:
            lines.append(f"  - {v}")
        return "\n".join(lines)


def check(
    problem: JsonInput,
    solution: JsonInput,
    matrices: Optional[Iterable[JsonInput]] = None,
) -> CheckResult:
    """Check that *solution* is feasible with respect to *problem* and *matrices*.

    The checker verifies load capacity, time-window adherence, relation
    constraints, break/reload assignments, routing consistency, and vehicle
    limits.

    Parameters
    ----------
    problem:
        The VRP problem definition.
    solution:
        The solver output to verify.
    matrices:
        Optional routing matrices.

    Returns
    -------
    CheckResult
        Empty violations list means feasible.

    Raises
    ------
    OSError
        If *problem* or *solution* cannot be parsed.
    """
    from . import _vrp_cli as vrp_cli

    problem_asset = _ensure_asset(problem, Problem)
    solution_asset = _ensure_asset(solution, Solution)
    matrix_assets = [_ensure_asset(m, RoutingMatrix) for m in matrices or []]

    raw = vrp_cli.check_pragmatic_solution(
        problem_asset.to_json(),
        solution_asset.to_json(),
        [m.to_json() for m in matrix_assets],
    )
    violations: List[str] = json.loads(raw)
    return CheckResult(violations)




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

    if isinstance(location, int):
        return {"index": location}

    if isinstance(location, (list, tuple)) and len(location) == 2:
        return {"lat": location[0], "lng": location[1]}

    if hasattr(location, "lat") and hasattr(location, "lng"):
        return {"lat": location.lat, "lng": location.lng}

    raise ValueError("location must be a dict, an integer index, a (lat, lng) pair, or an object with lat/lng attributes")


def _read_json(source: JsonInput) -> JsonData:
    if isinstance(source, JsonAsset):
        return source.to_dict()

    if isinstance(source, (dict, list)):
        return deepcopy(source)

    if not isinstance(source, (str, Path)):
        return _to_jsonable(source)

    # If it looks like a JSON literal, parse it directly (avoids false-positive path hits)
    if isinstance(source, str) and source.lstrip()[:1] in ("{", "["):
        return json.loads(source)

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
