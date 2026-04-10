import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentorch import EvolutionConfig, EvolutionManager, EvaluationResult, Genome, SearchSpace


async def build_candidate(genome: Genome) -> dict:
    return {"system_config": genome.genes}


async def evaluate_candidate(genome: Genome, candidate: dict, tasks: list[str]) -> EvaluationResult:
    genes = candidate["system_config"]
    fitness = 0.0
    if genes["planner"]["reasoning_kind"] == "plan_execute":
        fitness += 2.0
    if genes["memory"]["promotion_min_support_agents"] == 2:
        fitness += 1.0
    if genes["tools"]["tool_policy"] == "tool_first":
        fitness += 1.0
    fitness += 0.1 * len(tasks)
    return EvaluationResult(
        genome_id=genome.id,
        fitness=fitness,
        metrics={"task_count": float(len(tasks)), "fitness": fitness},
    )


async def main() -> None:
    manager = EvolutionManager(
        builder=build_candidate,
        evaluator=evaluate_candidate,
        search_space=SearchSpace(
            {
                "planner.reasoning_kind": ["react", "plan_execute", "reflexion"],
                "memory.promotion_min_support_agents": [1, 2, 3],
                "tools.tool_policy": ["tool_first", "reason_first"],
            }
        ),
        config=EvolutionConfig(
            population_size=6,
            generations=4,
            mutation_rate=0.5,
            elitism=1,
            seed=11,
        ),
    )

    result = await manager.evolve(
        tasks=[
            "plan a multi-agent workflow",
            "review a design proposal",
            "improve collective memory quality",
        ]
    )

    print("=== Best Genome ===")
    print(result.best_genome.model_dump())
    print()
    print("=== Best Evaluation ===")
    print(result.best_evaluation.model_dump())
    print()
    print("=== Generation History ===")
    for generation in result.history:
        print(
            {
                "generation": generation.generation,
                "best_genome_id": generation.best_genome_id,
                "best_fitness": generation.best_fitness,
            }
        )


if __name__ == "__main__":
    asyncio.run(main())
