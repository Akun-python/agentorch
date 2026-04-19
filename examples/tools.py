import asyncio
from pathlib import Path
from pprint import pprint
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agentorch import Agent, IndexedKnowledgeBase, SandboxManager, ToolRegistry
from agentorch.config import RuntimeConfig
from agentorch.knowledge import Document, RagStrategyConfig
from agentorch.sandbox import SandboxPolicy
from agentorch.strategies import ContextPolicy


PROMPT = (
    "Please introduce yourself in one sentence, then inspect the current "
    "working directory and briefly list the files you find."
)


async def main() -> None:
    sandbox = SandboxManager(
        policy=SandboxPolicy(
            allowed_paths=[Path.cwd()],
            command_allowlist=["python", "git", "powershell", "cmd"],
            timeout=15.0,
        )
    )

    tools = ToolRegistry.with_bundles(
        workspace_root=Path.cwd(),
        sandbox=sandbox,
    )

    knowledge_base = await IndexedKnowledgeBase.acreate(
        documents=[
            Document(
                id="doc-1",
                text="agentorch supports runtime, tools, memory, workflows, reasoning, and multi-agent orchestration.",
                metadata={"scopes": ["overview"]},
            ),
            Document(
                id="doc-2",
                text="Deliberative RAG can route sources and validate coverage before returning evidence.",
                metadata={"scopes": ["overview", "rag"]},
            ),
        ]
    )

    runtime_config = RuntimeConfig.agent(
        reasoning="react",
        context_policy=ContextPolicy.lean(),
        rag=RagStrategyConfig.for_deliberative(
            knowledge_scope=["overview"],
            max_steps=1,
        ),
        max_steps=4,
    )

    agent = await Agent.acreate(
        model_config="gpt-4.1-mini",
        tools=tools,
        sandbox=sandbox,
        knowledge_base=knowledge_base,
        config=runtime_config,
    )

    call_logs: list[dict[str, object]] = []
    original_generate = agent.runtime.model.generate

    async def traced_generate(request):
        call_index = len(call_logs) + 1
        response = await original_generate(request)
        usage = response.usage
        tool_calls = response.tool_calls or []

        item = {
            "call_index": call_index,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "finish_reason": response.finish_reason,
            "tool_calls": len(tool_calls),
            "content_preview": (response.content or "")[:200],
        }
        call_logs.append(item)

        print(f"\n========== Model Call #{call_index} ==========")
        print(f"prompt_tokens: {usage.prompt_tokens}")
        print(f"completion_tokens: {usage.completion_tokens}")
        print(f"total_tokens: {usage.total_tokens}")
        print(f"finish_reason: {response.finish_reason}")
        print(f"tool_calls: {len(tool_calls)}")

        if tool_calls:
            print("planned tool calls:")
            for tool_call in tool_calls:
                print(f"  tool_name: {tool_call.name}")
                print(f"  tool_call_id: {tool_call.id}")
                print("  arguments:")
                pprint(tool_call.arguments)

        if response.content:
            print("content preview:")
            print(response.content[:300])

        return response

    agent.runtime.model.generate = traced_generate

    final_result = None

    try:
        async for event in agent.run(
            PROMPT,
            thread_id="tool-trace-1",
            stream=True,
        ):
            print(f"\n==================== Event: {event.event_type} ====================")

            if event.payload:
                pprint(event.payload)

            if event.tool_calls:
                print("tool_calls:")
                for tool_call in event.tool_calls:
                    print(f"  tool_name: {tool_call.name}")
                    print(f"  tool_call_id: {tool_call.id}")
                    print("  arguments:")
                    pprint(tool_call.arguments)

            if event.delta_text:
                print("delta_text:")
                print(event.delta_text)

            if event.event_type == "final_result" and event.result is not None:
                final_result = event.result
    finally:
        await agent.aclose()

    print("\n\n========== Final Output ==========")
    if final_result is not None:
        print(final_result.output_text)

        print("\n========== Final Token Usage ==========")
        print(f"prompt_tokens: {final_result.usage.prompt_tokens}")
        print(f"completion_tokens: {final_result.usage.completion_tokens}")
        print(f"total_tokens: {final_result.usage.total_tokens}")

        print("\n========== Final Tool Results ==========")
        for index, tool_result in enumerate(final_result.tool_results, start=1):
            print(f"\nTool #{index}")
            print(f"tool_name: {tool_result.tool_name}")
            print(f"is_error: {tool_result.is_error}")
            print(f"error_message: {tool_result.error_message}")
            print(f"duration: {tool_result.duration}")
            print("output:")
            pprint(tool_result.output)

    print("\n========== Per-call Token Usage ==========")
    for item in call_logs:
        print(
            f"call {item['call_index']} | "
            f"prompt: {item['prompt_tokens']} | "
            f"completion: {item['completion_tokens']} | "
            f"total: {item['total_tokens']} | "
            f"finish_reason: {item['finish_reason']} | "
            f"tool_calls: {item['tool_calls']}"
        )


if __name__ == "__main__":
    asyncio.run(main())
