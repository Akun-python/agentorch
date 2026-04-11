from __future__ import annotations

import inspect
import random
from typing import Any

from .context import BuilderFn, EvolutionExecutionContext, EvaluatorFn
from .bootstrap import bootstrap_evolution_defaults
from .factory import create_evolution_algorithm
from .search_space import SearchSpace
from .types import EvaluationResult, EvolutionConfig, EvolutionResult, Genome


class EvolutionManager:
    def __init__(
        self,
        *,
        builder: BuilderFn,
        evaluator: EvaluatorFn,
        config: EvolutionConfig | None = None,
        search_space: SearchSpace | dict[str, list[Any]] | None = None,
    ) -> None:
        self.builder = builder
        self.evaluator = evaluator
        self.config = config or EvolutionConfig()
        if search_space is None:
            raise ValueError("EvolutionManager requires a search_space for population initialization and mutation.")
        self.search_space = search_space if isinstance(search_space, SearchSpace) else SearchSpace(search_space)
        self._rng = random.Random(self.config.seed)
        bootstrap_evolution_defaults()
        self.algorithm = create_evolution_algorithm(
            self.config.algorithm_kind,
            search_space=self.search_space,
            config=self.config,
            **self.config.algorithm_config,
        )

    async def evolve(
        self,
        *,
        tasks: list[Any] | None = None,
        initial_population: list[Genome] | None = None,
    ) -> EvolutionResult:
        context = EvolutionExecutionContext(
            builder=self.builder,
            evaluator=self.evaluator,
            config=self.config,
            search_space=self.search_space,
            rng=self._rng,
        )
        return await self.algorithm.evolve(context, tasks=tasks, initial_population=initial_population)

    async def build_candidate(self, genome: Genome) -> Any:
        return await self._resolve(self.builder(genome))

    async def _resolve(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value
