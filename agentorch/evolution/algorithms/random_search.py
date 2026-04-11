from __future__ import annotations

from typing import Any

from agentorch.evolution.base import EvolutionAlgorithm
from agentorch.evolution.context import EvolutionExecutionContext
from agentorch.evolution.types import EvaluationResult, EvolutionResult, GenerationResult, Genome


class RandomSearchEvolutionAlgorithm(EvolutionAlgorithm):
    async def evolve(
        self,
        context: EvolutionExecutionContext,
        *,
        tasks: list[Any] | None = None,
        initial_population: list[Genome] | None = None,
    ) -> EvolutionResult:
        tasks = tasks or []
        budget = context.config.evaluation_budget or (context.config.population_size * context.config.generations)
        history: list[GenerationResult] = []
        best_genome: Genome | None = None
        best_evaluation: EvaluationResult | None = None
        evaluated = 0
        generation = 0
        while evaluated < budget:
            remaining = budget - evaluated
            batch_size = min(context.config.population_size, remaining)
            population = [
                Genome(id=f"random-{generation}-{index}", generation=generation, genes=context.search_space.sample(context.rng))
                for index in range(batch_size)
            ]
            evaluations: list[EvaluationResult] = []
            for genome in population:
                candidate = await context.resolve(context.builder(genome))
                evaluation = await context.resolve(context.evaluator(genome, candidate, tasks))
                genome.fitness = evaluation.fitness
                evaluations.append(evaluation)
                evaluated += 1
                if best_evaluation is None or evaluation.fitness > best_evaluation.fitness:
                    best_genome = genome.model_copy(deep=True)
                    best_evaluation = evaluation.model_copy(deep=True)
            if context.config.retain_history:
                history.append(
                    GenerationResult(
                        generation=generation,
                        population=[item.model_copy(deep=True) for item in population],
                        evaluations=[item.model_copy(deep=True) for item in evaluations],
                        best_genome_id=max(population, key=lambda item: item.fitness or float("-inf")).id if population else None,
                        best_fitness=max((item.fitness or float("-inf") for item in population), default=None),
                    )
                )
            generation += 1
        if best_genome is None or best_evaluation is None:
            raise RuntimeError("Random search did not evaluate any genomes.")
        return EvolutionResult(best_genome=best_genome, best_evaluation=best_evaluation, history=history)
