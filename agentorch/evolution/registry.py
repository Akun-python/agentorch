from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .base import EvolutionAlgorithm

EvolutionAlgorithmFactory = Callable[..., EvolutionAlgorithm]


@dataclass
class EvolutionRegistration:
    kind: str
    algorithm_cls: type[EvolutionAlgorithm] | None = None
    factory: EvolutionAlgorithmFactory | None = None


class EvolutionRegistry:
    def __init__(self) -> None:
        self._algorithms: dict[str, EvolutionRegistration] = {}

    def register(
        self,
        kind: str,
        algorithm_cls: type[EvolutionAlgorithm] | None = None,
        *,
        factory: EvolutionAlgorithmFactory | None = None,
    ) -> None:
        normalized = str(kind)
        if algorithm_cls is None and factory is None:
            raise ValueError("register_evolution_algorithm requires an algorithm class or factory.")
        self._algorithms[normalized] = EvolutionRegistration(kind=normalized, algorithm_cls=algorithm_cls, factory=factory)

    def get(self, kind: str) -> EvolutionRegistration:
        try:
            return self._algorithms[str(kind)]
        except KeyError as exc:
            raise ValueError(f"Unsupported evolution algorithm: {kind}") from exc

    def list(self) -> list[str]:
        return sorted(self._algorithms.keys())

    def create(self, kind: str, **kwargs: Any) -> EvolutionAlgorithm:
        registration = self.get(kind)
        if registration.factory is not None:
            return registration.factory(**kwargs)
        if registration.algorithm_cls is None:
            raise ValueError(f"Evolution algorithm '{kind}' has no implementation class.")
        try:
            return registration.algorithm_cls(**kwargs)
        except TypeError:
            return registration.algorithm_cls()


default_evolution_registry = EvolutionRegistry()


def register_evolution_algorithm(
    kind: str,
    algorithm_cls: type[EvolutionAlgorithm] | None,
    *,
    factory: EvolutionAlgorithmFactory | None = None,
) -> None:
    default_evolution_registry.register(kind, algorithm_cls, factory=factory)


def get_evolution_algorithm_registration(kind: str) -> EvolutionRegistration:
    return default_evolution_registry.get(kind)


def list_evolution_algorithms() -> list[str]:
    return default_evolution_registry.list()
