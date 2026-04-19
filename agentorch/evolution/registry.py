from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable

from agentorch._component_registry import ComponentRegistry

from .base import EvolutionAlgorithm

EvolutionAlgorithmFactory = Callable[..., EvolutionAlgorithm]


@dataclass
class EvolutionRegistration:
    kind: str
    algorithm_cls: type[EvolutionAlgorithm] | None = None
    factory: EvolutionAlgorithmFactory | None = None


def _create_evolution_from_registration(
    registration: EvolutionRegistration,
    algorithm_cls: type[EvolutionAlgorithm],
    kwargs: dict[str, Any],
) -> EvolutionAlgorithm:
    try:
        return algorithm_cls(**kwargs)
    except TypeError:
        return algorithm_cls()


class EvolutionRegistry(ComponentRegistry[EvolutionRegistration, type[EvolutionAlgorithm]]):
    def __init__(self) -> None:
        super().__init__(
            EvolutionRegistration,
            implementation_attr="algorithm_cls",
            register_error="register_evolution_algorithm requires an algorithm class or factory.",
            unsupported_error="Unsupported evolution algorithm: {kind}",
            missing_implementation_error="Evolution algorithm '{kind}' has no implementation class.",
            creator=_create_evolution_from_registration,
        )

    def register(
        self,
        kind: str,
        algorithm_cls: type[EvolutionAlgorithm] | None = None,
        *,
        factory: EvolutionAlgorithmFactory | None = None,
    ) -> None:
        super().register(kind, algorithm_cls, factory=factory)


def _ensure_evolution_defaults_registered() -> None:
    bootstrap_module = import_module(f"{__package__}.bootstrap")
    bootstrap_module.bootstrap_evolution_defaults()


default_evolution_registry = EvolutionRegistry()


def register_evolution_algorithm(
    kind: str,
    algorithm_cls: type[EvolutionAlgorithm] | None,
    *,
    factory: EvolutionAlgorithmFactory | None = None,
) -> None:
    default_evolution_registry.register(kind, algorithm_cls, factory=factory)


def get_evolution_algorithm_registration(kind: str) -> EvolutionRegistration:
    _ensure_evolution_defaults_registered()
    return default_evolution_registry.get(kind)


def list_evolution_algorithms() -> list[str]:
    _ensure_evolution_defaults_registered()
    return default_evolution_registry.list()
