import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentorch import EvaluationResult, EvolutionConfig, MemoryManager, SearchSpace, create_agent_evolution
from agentorch.config import MemoryConfig
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.models.base import BaseModelAdapter


def _example_memory_root(name: str) -> Path:
    root = Path(__file__).resolve().parents[1] / ".agentorch_examples" / name
    root.mkdir(parents=True, exist_ok=True)
    return root


class DemoModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        latest_user = next((message.content for message in reversed(request.messages) if message.role == "user"), "")
        content = f"Facade demo answer: {latest_user or 'no user input'}"
        return ModelResponse(
            message=Message(role="assistant", content=content),
            content=content,
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


def _score_candidate(genome, candidate, tasks):
    reasoning_kind = candidate.runtime.config.reasoning_strategy.kind.value
    workflow_nodes = [node.kind for node in candidate.workflow.nodes] if candidate.workflow is not None else []
    fitness = float(len(tasks))
    if reasoning_kind == "plan_execute":
        fitness += 2.0
    if workflow_nodes == ["model"]:
        fitness += 1.0
    return EvaluationResult(
        genome_id=genome.id,
        fitness=fitness,
        metrics={
            "task_count": float(len(tasks)),
            "uses_plan_execute": 1.0 if reasoning_kind == "plan_execute" else 0.0,
            "has_model_only_workflow": 1.0 if workflow_nodes == ["model"] else 0.0,
        },
    )


async def main() -> None:
    memory_root = _example_memory_root("evolution_facade_demo")
    memory = MemoryManager(
        config=MemoryConfig(
            checkpoint_path=memory_root / "checkpoints.db",
            record_path=memory_root / "records.db",
        )
    )

    session = create_agent_evolution(
        model=DemoModel(),
        system_prompt="You are the best agent found by the facade evolution demo.",
        memory=memory,
        search_space=SearchSpace(
            {
                "reasoning.kind": ["react", "plan_execute"],
                "workflow.template": ["classic_inline_answer"],
            }
        ),
        evolution_config=EvolutionConfig(
            population_size=4,
            generations=2,
            mutation_rate=0.4,
            elitism=1,
            seed=7,
        ),
        tasks=[
            "Summarize a plan for a user.",
            "Produce a compact implementation outline.",
        ],
        evaluator=_score_candidate,
    )

    result = await session.evolve()
    best_agent = await session.build_best_candidate(result)
    try:
        run_result = await best_agent.run(
            "Describe the evolved facade configuration in one sentence.",
            thread_id="example-evolution-facade",
        )
        run_payload = json.loads(run_result.output_text)
        payload = {
            "best_genome": result.best_genome.model_dump(),
            "best_evaluation": result.best_evaluation.model_dump(),
            "best_agent": {
                "reasoning_kind": best_agent.runtime.config.reasoning_strategy.kind.value,
                "workflow_nodes": [node.kind for node in best_agent.workflow.nodes] if best_agent.workflow is not None else [],
                "run_output": run_payload["output_text"],
            },
            "memory_root": str(memory_root),
        }
        print("=== Facade Evolution Demo ===")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    finally:
        await best_agent.aclose()


if __name__ == "__main__":
    asyncio.run(main())
