import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentorch import EvolutionConfig, EvolutionManager, EvaluationResult, Genome, SearchSpace


async def build_candidate(genome: Genome) -> dict:
    return {"genes": genome.genes}


async def evaluate_candidate(genome: Genome, candidate: dict, tasks: list[str]) -> EvaluationResult:
    genes = candidate["genes"]
    fitness = 0.0
    if genes.get("reasoning", {}).get("kind") == "plan_execute":
        fitness += 2.0
    if genes.get("rag", {}).get("mode") == "hybrid":
        fitness += 2.0
    if genes.get("workflow", {}).get("template") == "retrieve_plan_review":
        fitness += 1.0
    return EvaluationResult(genome_id=genome.id, fitness=fitness, metrics={"fitness": fitness})


async def main() -> None:
    for algorithm in ("random_search", "hill_climb", "beam_search", "genetic"):
        manager = EvolutionManager(
            builder=build_candidate,
            evaluator=evaluate_candidate,
            search_space=SearchSpace(
                {
                    "reasoning.kind": ["react", "plan_execute"],
                    "rag.mode": ["classic", "hybrid"],
                    "workflow.template": ["classic_inline_answer", "retrieve_plan_review"],
                }
            ),
            config=EvolutionConfig(algorithm_kind=algorithm, population_size=4, generations=3, evaluation_budget=6, seed=7),
        )
        result = await manager.evolve(tasks=["a", "b"])
        print(f"=== {algorithm} ===")
        print(result.best_genome.model_dump())


if __name__ == "__main__":
    asyncio.run(main())
