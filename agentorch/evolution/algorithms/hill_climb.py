from __future__ import annotations

from typing import Any

from agentorch.evolution.base import EvolutionAlgorithm
from agentorch.evolution.context import EvolutionExecutionContext
from agentorch.evolution.types import EvaluationResult, EvolutionResult, GenerationResult, Genome


class HillClimbEvolutionAlgorithm(EvolutionAlgorithm):
    async def evolve(
        self,
        context: EvolutionExecutionContext,
        *,
        tasks: list[Any] | None = None,
        initial_population: list[Genome] | None = None,
    ) -> EvolutionResult:
        tasks = tasks or []
        current = (initial_population or context.initialize_population())[0].model_copy(deep=True)
        best_genome: Genome | None = None
        best_evaluation: EvaluationResult | None = None
        history: list[GenerationResult] = []
        stale_rounds = 0
        for generation in range(context.config.generations):
            current.generation = generation
            candidate = await context.resolve(context.builder(current))
            evaluation = await context.resolve(context.evaluator(current, candidate, tasks))
            current.fitness = evaluation.fitness
            if best_evaluation is None or evaluation.fitness > best_evaluation.fitness:
                best_genome = current.model_copy(deep=True)
                best_evaluation = evaluation.model_copy(deep=True)
                stale_rounds = 0
            else:
                stale_rounds += 1
            if context.config.retain_history:
                history.append(
                    GenerationResult(
                        generation=generation,
                        population=[current.model_copy(deep=True)],
                        evaluations=[evaluation.model_copy(deep=True)],
                        best_genome_id=current.id,
                        best_fitness=current.fitness,
                    )
                )
            if context.config.early_stop_patience is not None and stale_rounds >= context.config.early_stop_patience:
                break
            current = context.search_space.neighbor(current, rng=context.rng, child_id=f"hill-{generation + 1}", generation=generation + 1)
        if best_genome is None or best_evaluation is None:
            raise RuntimeError("Hill climbing did not evaluate any genomes.")
        return EvolutionResult(best_genome=best_genome, best_evaluation=best_evaluation, history=history)
