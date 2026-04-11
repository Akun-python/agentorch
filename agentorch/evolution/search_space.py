from __future__ import annotations

import copy
import random
from typing import Any

from .types import Genome


def _set_nested(target: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    current = target
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value


class SearchSpace:
    """Discrete search space for agent/system-level evolution."""

    def __init__(self, dimensions: dict[str, list[Any]]) -> None:
        if not dimensions:
            raise ValueError("SearchSpace requires at least one dimension.")
        normalized: dict[str, list[Any]] = {}
        for key, values in dimensions.items():
            if not values:
                raise ValueError(f"Search space dimension '{key}' cannot be empty.")
            normalized[key] = list(values)
        self.dimensions = normalized

    def sample(self, rng: random.Random) -> dict[str, Any]:
        genes: dict[str, Any] = {}
        for key, values in self.dimensions.items():
            _set_nested(genes, key, rng.choice(values))
        return genes

    def mutate(self, genes: dict[str, Any], *, rng: random.Random, mutation_rate: float) -> dict[str, Any]:
        mutated = copy.deepcopy(genes)
        for key, values in self.dimensions.items():
            if rng.random() > mutation_rate:
                continue
            _set_nested(mutated, key, rng.choice(values))
        return mutated

    def neighbor(self, genome: Genome, *, rng: random.Random, child_id: str, generation: int) -> Genome:
        key = rng.choice(list(self.dimensions.keys()))
        genes = copy.deepcopy(genome.genes)
        _set_nested(genes, key, rng.choice(self.dimensions[key]))
        metadata = copy.deepcopy(genome.metadata)
        metadata.setdefault("neighbor_history", []).append({"generation": generation, "dimension": key})
        return Genome(
            id=child_id,
            generation=generation,
            parent_ids=[genome.id],
            genes=genes,
            metadata=metadata,
        )
