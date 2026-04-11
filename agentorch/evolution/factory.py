from __future__ import annotations

from typing import Any

from .bootstrap import bootstrap_evolution_defaults
from .registry import default_evolution_registry


class EvolutionFactory:
    @staticmethod
    def create(kind: str, **kwargs: Any):
        bootstrap_evolution_defaults()
        return default_evolution_registry.create(kind, **kwargs)


def create_evolution_algorithm(kind: str, **kwargs: Any):
    return EvolutionFactory.create(kind, **kwargs)
