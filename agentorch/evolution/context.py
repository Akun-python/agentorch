from __future__ import annotations

import inspect
from dataclasses import dataclass
from random import Random
from typing import Any, Awaitable, Callable

from .search_space import SearchSpace
from .types import EvaluationResult, EvolutionConfig, Genome

BuilderFn = Callable[[Genome], Any]
EvaluatorFn = Callable[[Genome, Any, list[Any]], EvaluationResult | Awaitable[EvaluationResult]]


@dataclass
class EvolutionExecutionContext:
    builder: BuilderFn
    evaluator: EvaluatorFn
    config: EvolutionConfig
    search_space: SearchSpace
    rng: Random

    def initialize_population(self) -> list[Genome]:
        return [
            Genome(
                id=f"genome-{index + 1}",
                generation=0,
                genes=self.search_space.sample(self.rng),
            )
            for index in range(self.config.population_size)
        ]

    async def resolve(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value
