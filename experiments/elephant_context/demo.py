from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agentorch import Agent, AgentCapability, AgentRegistry, AgentSpec, MemoryManager, Runtime, Supervisor
from agentorch.config import MemoryConfig
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.models.base import BaseModelAdapter
from agentorch.observability import EventBus, Tracer

from experiments.elephant_context import build_elephant_runtime_config


class SystemPromptEchoModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        system_message = next(message for message in request.messages if message.role == "system")
        return ModelResponse(
            message=Message(role="assistant", content=system_message.content),
            content=system_message.content,
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


class CollectiveMemoryFocusModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        system_message = next(message for message in request.messages if message.role == "system")
        content = system_message.content
        start = content.find("Collective Memory:")
        end = content.find("Retrieved Evidence:")
        focused = content[start:end].strip() if start != -1 and end != -1 else content
        return ModelResponse(
            message=Message(role="assistant", content=focused),
            content=focused,
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


async def build_specialist() -> Agent:
    return Agent(runtime=Runtime(model=CollectiveMemoryFocusModel(), tracer=Tracer(EventBus())))


async def main() -> None:
    temp_root = Path(".agentorch") / "elephant_context_demo"
    temp_root.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    config = MemoryConfig(
        checkpoint_path=temp_root / f"checkpoints_{run_id}.db",
        record_path=temp_root / f"records_{run_id}.db",
    )
    shared_memory = MemoryManager(config=config)
    seeded_id = await shared_memory.promote_collective_memory(
        thread_id="elephant-demo-thread",
        kind="route",
        content="follow the dry riverbed to reach the safe checkpoint",
        tags=["route", "hazard"],
        source_agents=["elder"],
        confidence=0.85,
        scope="planning",
    )

    registry = AgentRegistry()
    registry.register(
        AgentSpec(
            name="planner",
            description="Planning specialist",
            tags=["plan"],
            capabilities=[AgentCapability.PLAN],
            allowed_knowledge_scopes=["planning"],
        ),
        await build_specialist(),
    )
    registry.register(
        AgentSpec(
            name="reviewer",
            description="Review specialist",
            tags=["review"],
            capabilities=[AgentCapability.REVIEW],
            allowed_knowledge_scopes=["planning"],
        ),
        await build_specialist(),
    )

    runtime = Runtime(
        model=SystemPromptEchoModel(),
        memory=shared_memory,
        agent_registry=registry,
        supervisor=Supervisor(registry=registry),
        tracer=Tracer(EventBus()),
        config=build_elephant_runtime_config(default_knowledge_scope=["planning"]),
    )
    agent = Agent(runtime=runtime)
    result = await agent.run("plan review the safe checkpoint route", thread_id="elephant-demo-thread")

    records = await shared_memory.search_collective_memory(
        query="dry riverbed",
        thread_id="elephant-demo-thread",
        status=None,
        limit=20,
    )
    seeded = next(item for item in records if item["id"] == seeded_id)
    promoted = [item for item in records if item["id"] != seeded_id]

    print("=== Elephant Plugin Output Preview ===")
    print(result.output_text[:800])
    print()
    print("=== Seeded Memory After Reuse ===")
    print(
        {
            "id": seeded["id"],
            "kind": seeded["kind"],
            "status": seeded["status"],
            "reuse_count": seeded["reuse_count"],
            "source_agents": seeded["source_agents"],
        }
    )
    print()
    print("=== Newly Promoted Collective Memory ===")
    if not promoted:
        print("No new collective memory was promoted.")
    for item in promoted:
        print(
            {
                "id": item["id"],
                "memory_role": item["memory_role"],
                "status": item["status"],
                "kind": item["kind"],
                "source_agents": item["source_agents"],
                "content_preview": item["content"][:160],
            }
        )


if __name__ == "__main__":
    asyncio.run(main())
