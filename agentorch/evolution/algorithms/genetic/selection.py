from __future__ import annotations

from typing import Sequence

from agentorch.evolution.types import Genome


class TopKSelection:
    def select(self, population: Sequence[Genome], *, count: int) -> list[Genome]:
        ordered = sorted(population, key=lambda genome: genome.fitness if genome.fitness is not None else float("-inf"), reverse=True)
        return [genome.model_copy(deep=True) for genome in ordered[:count]]
