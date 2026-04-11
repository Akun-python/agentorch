from __future__ import annotations

import random

from agentorch.evolution.types import Genome


class MutationOperator:
    def __init__(self, search_space) -> None:
        self.search_space = search_space

    def mutate(self, genome: Genome, *, rng: random.Random, mutation_rate: float, child_id: str, generation: int) -> Genome:
        mutated_genes = self.search_space.mutate(genome.genes, rng=rng, mutation_rate=mutation_rate)
        metadata = dict(genome.metadata)
        mutation_history = list(metadata.get("mutation_history", []))
        mutation_history.append({"generation": generation, "rate": mutation_rate})
        metadata["mutation_history"] = mutation_history
        return Genome(
            id=child_id,
            generation=generation,
            parent_ids=[genome.id],
            genes=mutated_genes,
            metadata=metadata,
        )
