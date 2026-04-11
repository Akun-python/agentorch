from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .types import EvolutionResult, Genome


class EvolutionAlgorithm(ABC):
    @abstractmethod
    async def evolve(
        self,
        context: Any,
        *,
        tasks: list[Any] | None = None,
        initial_population: list[Genome] | None = None,
    ) -> EvolutionResult:
        raise NotImplementedError
