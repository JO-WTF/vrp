# Contains semi-automatically generated model of config format.

from __future__ import annotations
from pydantic.dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Telemetry:
    progress: Progress


@dataclass
class Progress:
    enabled: bool
    logBest: int
    logPopulation: int
    dumpPopulation: bool


Telemetry.__pydantic_model__.update_forward_refs()


@dataclass
class Config:
    evolution: Optional[Dict[str, Any]] = None
    hyper: Optional[Dict[str, Any]] = None
    termination: Optional[Termination] = None
    telemetry: Optional[Telemetry] = Telemetry(
        progress=Progress(
            enabled=True,
            logBest=100,
            logPopulation=1000,
            dumpPopulation=False
        )
    )
    environment: Optional[Environment] = None
    output: Optional[Output] = None


@dataclass
class Termination:
    maxTime: Optional[int] = None
    maxGenerations: Optional[int] = None


@dataclass
class Logging:
    enabled: bool


Logging.__pydantic_model__.update_forward_refs()


@dataclass
class Environment:
    logging: Logging = Logging(enabled=True)
    parallelism: Optional[int] = None
    maxTime: Optional[int] = None
    isProfiling: Optional[bool] = None
    isExperimental: Optional[bool] = None


@dataclass
class Output:
    includeGeoJson: Optional[bool] = None
    writer: Optional[Dict[str, Any]] = None
    extras: Optional[List[str]] = None


Config.__pydantic_model__.update_forward_refs()
Telemetry.__pydantic_model__.update_forward_refs()
Termination.__pydantic_model__.update_forward_refs()
Environment.__pydantic_model__.update_forward_refs()
Output.__pydantic_model__.update_forward_refs()
