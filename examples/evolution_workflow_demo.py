import asyncio
import json
import sys
from pathlib import Path

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentorch import Agent, EvaluationResult, EvolutionConfig, MemoryManager, Runtime, SearchSpace, ToolRegistry, create_agent_evolution, tool
from agentorch.config import MemoryConfig
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.models.base import BaseModelAdapter
from agentorch.workflow import Node, WorkflowBuilder


def _example_memory_root(name: str) -> Path:
    root = Path(__file__).resolve().parents[1] / ".agentorch_examples" / name
    root.mkdir(parents=True, exist_ok=True)
    return root


class EmptyInput(BaseModel):
    value: str | None = None


@tool(description="Emit a deterministic seed payload for the workflow demo.")
async def emit_design_seed(input: EmptyInput):
    return {
        "topic": "workflow-demo",
        "artifact_name": "workflow-evolution-summary",
        "required_sections": ["best_candidate", "artifact_id", "model_report"],
    }


class WorkflowDigestModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        system_message = next((message.content for message in request.messages if message.role == "system"), "")
        flags = {
            "task_packet_present": "Task Packet:" in system_message,
            "tool_seed_seen": "workflow-evolution-summary" in system_message,
            "evolution_result_seen": "best_candidate" in system_message and "best_evaluation" in system_message,
        }
        content = "Workflow context digest: " + json.dumps(flags, ensure_ascii=False)
        return ModelResponse(
            message=Message(role="assistant", content=content),
            content=content,
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


def _score_candidate(genome, candidate, tasks):
    workflow_nodes = [node.kind for node in candidate.workflow.nodes] if candidate.workflow is not None else []
    fitness = float(len(tasks))
    if workflow_nodes and workflow_nodes[0] == "retrieve":
        fitness += 3.0
    if candidate.runtime.config.reasoning_strategy.kind.value == "plan_execute":
        fitness += 1.0
    return EvaluationResult(
        genome_id=genome.id,
        fitness=fitness,
        metrics={
            "task_count": float(len(tasks)),
            "retrieve_first": 1.0 if workflow_nodes and workflow_nodes[0] == "retrieve" else 0.0,
        },
    )


async def main() -> None:
    memory_root = _example_memory_root("evolution_workflow_demo")
    memory = MemoryManager(
        config=MemoryConfig(
            checkpoint_path=memory_root / "checkpoints.db",
            record_path=memory_root / "records.db",
        )
    )

    session = create_agent_evolution(
        model=WorkflowDigestModel(),
        memory=memory,
        search_space=SearchSpace(
            {
                "reasoning.kind": ["react", "plan_execute"],
                "workflow.template": ["classic_inline_answer", "retrieve_plan_review"],
            }
        ),
        evolution_config=EvolutionConfig(population_size=4, generations=2, seed=9),
        tasks=[
            "Assemble a workflow-ready answer strategy.",
            "Prefer candidates that introduce an explicit retrieval step.",
        ],
        evaluator=_score_candidate,
    )

    tools = ToolRegistry.empty()
    tools.register(emit_design_seed)
    runtime = Runtime(
        model=WorkflowDigestModel(),
        tools=tools,
        memory=memory,
        config={
            "context_policy": {
                "sources": {
                    "memory_summary": True,
                    "retrieval_summary": True,
                    "retrieval_evidence": False,
                    "retrieval_citations": False,
                    "retrieval_report": False,
                    "retrieval_plan": False,
                    "tool_descriptions": False,
                    "skill_instructions": True,
                    "task_packet": {"enabled": True, "representation": "capsule"},
                    "delegation_context": {"enabled": True, "representation": "capsule"},
                    "shared_memory": {"enabled": True, "max_items": 4},
                },
                "char_budget": 60000,
                "overflow_action": "drop_low_priority",
            }
        },
    )
    workflow = (
        WorkflowBuilder(max_steps=8)
        .then(Node.tool("seed", "emit_design_seed"))
        .then(Node.evolution("search", session=session, include_history=False))
        .then(
            Node.model_node(
                "report",
                prompt="Summarize the workflow handoff using the workflow task packet.",
                task_context_from_variables=["seed", "search"],
            )
        )
        .then(Node.aggregate("bundle", sources=["seed", "search", "report"], output_key="bundle"))
        .then(
            Node(
                id="persist",
                kind="artifact",
                config={
                    "from_variable": "bundle",
                    "artifact_kind": "workflow_bundle",
                    "name": "evolution_workflow_demo",
                },
            )
        )
        .then(Node.aggregate("finalize", sources=["bundle", "persist"]))
        .build()
    )

    result = await Agent(runtime=runtime, workflow=workflow).run(
        "Compose an orchestration handoff packet.",
        thread_id="example-evolution-workflow",
    )
    payload = json.loads(result.output_text)
    bundle = payload["combined"]["bundle"]["combined"]
    summary = {
        "tool_output": bundle["seed"]["output"],
        "best_workflow_nodes": [node["kind"] for node in bundle["search"]["best_candidate"]["workflow"]["nodes"]],
        "model_report": bundle["report"]["output_text"],
        "artifact_id": payload["combined"]["persist"]["artifact_id"],
        "memory_root": str(memory_root),
    }
    print("=== Evolution Workflow Demo ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
