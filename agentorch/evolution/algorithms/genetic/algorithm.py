from __future__ import annotations

import uuid
from typing import Any

from agentorch.evolution.base import EvolutionAlgorithm
from agentorch.evolution.context import EvolutionExecutionContext
from agentorch.evolution.types import EvaluationResult, EvolutionResult, GenerationResult, Genome

from .mutation import MutationOperator
from .selection import TopKSelection


class GeneticEvolutionAlgorithm(EvolutionAlgorithm):
    def __init__(self, *, selection=None, mutation=None, **_: Any) -> None:
        self.selection = selection
        self.mutation = mutation

    async def evolve(
        self,
        context: EvolutionExecutionContext,
        *,
        tasks: list[Any] | None = None,
        initial_population: list[Genome] | None = None,
    ) -> EvolutionResult:
        tasks = tasks or []
        population = initial_population or context.initialize_population()
        history: list[GenerationResult] = []
        best_genome: Genome | None = None
        best_evaluation: EvaluationResult | None = None

        selection = self.selection or TopKSelection()
        mutation = self.mutation or MutationOperator(context.search_space)

        for generation in range(context.config.generations):
            current_population = [genome.model_copy(deep=True, update={"generation": generation}) for genome in population]
            evaluations: list[EvaluationResult] = []
            for genome in current_population:
                candidate = await context.resolve(context.builder(genome))
                evaluation = await context.resolve(context.evaluator(genome, candidate, tasks))
                genome.fitness = evaluation.fitness
                evaluations.append(evaluation)
                if best_evaluation is None or evaluation.fitness > best_evaluation.fitness:
                    best_genome = genome.model_copy(deep=True)
                    best_evaluation = evaluation.model_copy(deep=True)

            generation_result = GenerationResult(
                generation=generation,
                population=[genome.model_copy(deep=True) for genome in current_population],
                evaluations=[evaluation.model_copy(deep=True) for evaluation in evaluations],
            )
            best_current = max(current_population, key=lambda genome: genome.fitness if genome.fitness is not None else float("-inf"))
            generation_result.best_genome_id = best_current.id
            generation_result.best_fitness = best_current.fitness
            history.append(generation_result)

            if generation >= context.config.generations - 1:
                break
            population = self._next_generation(context, current_population, generation=generation + 1, selection=selection, mutation=mutation)

        if best_genome is None or best_evaluation is None:
            raise RuntimeError("Evolution did not produce any evaluation results.")
        return EvolutionResult(best_genome=best_genome, best_evaluation=best_evaluation, history=history)

    def _next_generation(
        self,
        context: EvolutionExecutionContext,
        population: list[Genome],
        *,
        generation: int,
        selection: TopKSelection,
        mutation: MutationOperator,
    ) -> list[Genome]:
        selection_size = context.config.selection_size or max(1, context.config.population_size // 2)
        selected = selection.select(population, count=selection_size)
        elites = selection.select(population, count=min(context.config.elitism, context.config.population_size))
        next_population: list[Genome] = []
        for elite in elites:
            next_population.append(
                elite.model_copy(
                    deep=True,
                    update={
                        "generation": generation,
                        "fitness": None,
                        "metadata": {**elite.metadata, "elite": True},
                    },
                )
            )
        while len(next_population) < context.config.population_size:
            parent = context.rng.choice(selected)
            child = mutation.mutate(
                parent,
                rng=context.rng,
                mutation_rate=context.config.mutation_rate,
                child_id=f"genome-{generation + 1}-{uuid.uuid4().hex[:8]}",
                generation=generation,
            )
            next_population.append(child)
        return next_population[: context.config.population_size]
