# Contains semi-automatically generated model of solver config format.

from __future__ import annotations
from pydantic.dataclasses import dataclass
from dataclasses import field
try:
    from pydantic.dataclasses import rebuild_dataclass
except ImportError:
    rebuild_dataclass = None
from typing import Any, Dict, Optional


def _update_forward_refs(*classes):
    for cls in classes:
        model = getattr(cls, "__pydantic_model__", None)

        if model is not None:
            model.update_forward_refs(**globals())
        elif rebuild_dataclass is not None:
            rebuild_dataclass(cls, _types_namespace=globals())


@dataclass
class Telemetry:
    progress: Optional[Progress] = None
    metrics: Optional[Metrics] = None


@dataclass
class Progress:
    enabled: bool
    logBest: Optional[int] = None
    logPopulation: Optional[int] = None


@dataclass
class Metrics:
    enabled: bool
    trackPopulation: Optional[int] = None


@dataclass
class Config:
    evolution: Optional[Evolution] = None
    hyper: Optional[Dict[str, Any]] = None
    termination: Optional[Termination] = None
    telemetry: Optional[Telemetry] = None
    environment: Optional[Environment] = None
    output: Optional[Output] = None


@dataclass
class Termination:
    maxTime: Optional[int] = None
    maxGenerations: Optional[int] = None
    variation: Optional[Variation] = None


@dataclass
class Variation:
    intervalType: str
    value: int
    cv: float
    isGlobal: bool = True


@dataclass
class Logging:
    enabled: bool
    prefix: Optional[str] = None


@dataclass
class Parallelism:
    numThreadPools: int
    threadsPerPool: int


@dataclass
class Environment:
    parallelism: Optional[Parallelism] = None
    logging: Optional[Logging] = None
    isExperimental: Optional[bool] = None


@dataclass
class Output:
    includeGeojson: Optional[bool] = None


@dataclass
class Initial:
    method: Dict[str, Any]
    alternatives: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Evolution:
    initial: Optional[Initial] = None
    population: Optional[Dict[str, Any]] = None


_update_forward_refs(
    Config,
    Telemetry,
    Progress,
    Metrics,
    Termination,
    Variation,
    Environment,
    Logging,
    Parallelism,
    Output,
    Initial,
    Evolution,
)
