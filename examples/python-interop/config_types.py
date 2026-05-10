# Contains semi-automatically generated non-complete model of config format.
# Please refer to documentation to define a full model

from __future__ import annotations
from pydantic.dataclasses import dataclass
try:
    from pydantic.dataclasses import rebuild_dataclass
except ImportError:
    rebuild_dataclass = None
from typing import Optional


def _update_forward_refs(*classes):
    for cls in classes:
        model = getattr(cls, "__pydantic_model__", None)

        if model is not None:
            model.update_forward_refs(**globals())
        elif rebuild_dataclass is not None:
            rebuild_dataclass(cls, _types_namespace=globals())


@dataclass
class Telemetry:
    progress: Progress


@dataclass
class Progress:
    enabled: bool
    logBest: int
    logPopulation: int
    dumpPopulation: bool


_update_forward_refs(Telemetry)


@dataclass
class Config:
    termination: Termination
    telemetry: Optional[Telemetry] = Telemetry(
        progress=Progress(
            enabled=True,
            logBest=100,
            logPopulation=1000,
            dumpPopulation=False
        )
    )
    environment: Optional[Environment] = None


@dataclass
class Termination:
    maxTime: Optional[int] = None
    maxGenerations: Optional[int] = None


@dataclass
class Logging:
    enabled: bool


_update_forward_refs(Logging)


@dataclass
class Environment:
    logging: Logging = Logging(enabled=True)
    isExperimental: Optional[bool] = None


_update_forward_refs(Config, Telemetry, Termination, Environment)
