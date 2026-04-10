import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentorch import EvolutionConfig, EvolutionManager, EvaluationResult, Genome, SearchSpace, candidate_from_genome


async def build_candidate(genome: Genome) -> dict:
    return candidate_from_genome(genome)


async def evaluate_candidate(genome: Genome, candidate: dict, tasks: list[str]) -> EvaluationResult:
    fitness = 0.0
    if candidate["reasoning_strategy"]["kind"] == "plan_execute":
        fitness += 2.0
    if candidate["rag_strategy"]["mode"] == "hybrid":
        fitness += 2.0
    if candidate["workflow_template"] == "retrieve_plan_review":
        fitness += 1.0
    return EvaluationResult(genome_id=genome.id, fitness=fitness, metrics={"fitness": fitness})


async def main() -> None:
    manager = EvolutionManager(
        builder=build_candidate,
        evaluator=evaluate_candidate,
        search_space=SearchSpace(
            {
                "reasoning.kind": ["react", "plan_execute"],
                "rag.mode": ["classic", "deliberative", "hybrid"],
                "rag.mount": ["inline", "workflow_only"],
                "workflow.template": ["classic_inline_answer", "retrieve_plan_review", "retrieve_delegate_aggregate"],
            }
        ),
        config=EvolutionConfig(algorithm_kind="beam_search", population_size=4, generations=4, seed=11),
    )
    result = await manager.evolve(tasks=["plan", "review"])
    print("=== Best Orchestration Genome ===")
    print(result.best_genome.model_dump())


if __name__ == "__main__":
    asyncio.run(main())
