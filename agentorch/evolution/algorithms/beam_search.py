from __future__ import annotations

from typing import Any

from agentorch.evolution.base import EvolutionAlgorithm
from agentorch.evolution.context import EvolutionExecutionContext
from agentorch.evolution.types import EvaluationResult, EvolutionResult, GenerationResult, Genome


class BeamSearchEvolutionAlgorithm(EvolutionAlgorithm):
    def __init__(self, *, beam_width: int = 3, expansions_per_parent: int = 2, **_: Any) -> None:
        self.beam_width = beam_width
        self.expansions_per_parent = expansions_per_parent

    async def evolve(
        self,
        context: EvolutionExecutionContext,
        *,
        tasks: list[Any] | None = None,
        initial_population: list[Genome] | None = None,
    ) -> EvolutionResult:
        tasks = tasks or []
        beam = (initial_population or context.initialize_population())[: self.beam_width]
        history: list[GenerationResult] = []
        best_genome: Genome | None = None
        best_evaluation: EvaluationResult | None = None
        stale_rounds = 0
        for generation in range(context.config.generations):
            evaluated_population: list[Genome] = []
            evaluations: list[EvaluationResult] = []
            for genome in beam:
                genome = genome.model_copy(deep=True, update={"generation": generation})
                candidate = await context.resolve(context.builder(genome))
                evaluation = await context.resolve(context.evaluator(genome, candidate, tasks))
                genome.fitness = evaluation.fitness
                evaluated_population.append(genome)
                evaluations.append(evaluation)
                if best_evaluation is None or evaluation.fitness > best_evaluation.fitness:
                    best_genome = genome.model_copy(deep=True)
                    best_evaluation = evaluation.model_copy(deep=True)
                    stale_rounds = 0
            if context.config.retain_history:
                history.append(
                    GenerationResult(
                        generation=generation,
                        population=[item.model_copy(deep=True) for item in evaluated_population],
                        evaluations=[item.model_copy(deep=True) for item in evaluations],
                        best_genome_id=max(evaluated_population, key=lambda item: item.fitness or float("-inf")).id if evaluated_population else None,
                        best_fitness=max((item.fitness or float("-inf") for item in evaluated_population), default=None),
                    )
                )
            if generation >= context.config.generations - 1:
                break
            if context.config.early_stop_patience is not None and stale_rounds >= context.config.early_stop_patience:
                break
            next_candidates: list[Genome] = []
            ranked = sorted(evaluated_population, key=lambda item: item.fitness or float("-inf"), reverse=True)[: self.beam_width]
            for parent in ranked:
                next_candidates.append(parent.model_copy(deep=True, update={"generation": generation + 1, "fitness": None}))
                for expansion in range(self.expansions_per_parent):
                    next_candidates.append(
                        context.search_space.neighbor(
                            parent,
                            rng=context.rng,
                            child_id=f"beam-{generation + 1}-{expansion}-{context.rng.randint(0, 999999)}",
                            generation=generation + 1,
                        )
                    )
            beam = next_candidates[: self.beam_width]
            stale_rounds += 1
        if best_genome is None or best_evaluation is None:
            raise RuntimeError("Beam search did not evaluate any genomes.")
        return EvolutionResult(best_genome=best_genome, best_evaluation=best_evaluation, history=history)
