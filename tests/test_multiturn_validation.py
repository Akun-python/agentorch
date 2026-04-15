import asyncio

from agentorch.config import validate_supported_python
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.memory import MemoryManager
from agentorch.models.base import BaseModelAdapter
from agentorch.runtime import Agent, Runtime


class ConstraintTrackingModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        user_messages = [message.content for message in request.messages if message.role == "user"]
        combined = "\n".join(user_messages)
        if "final coordination plan" not in combined:
            return ModelResponse(
                message=Message(role="assistant", content="noted"),
                content="noted",
                finish_reason="stop",
                usage=UsageInfo(total_tokens=1),
            )
        final_text = (
            f"Final constraints preserved: "
            f"{'Aurora-17' if 'Aurora-17' in combined else 'missing-codename'}, "
            f"{'800 words' if '800 words' in combined else 'missing-length'}, "
            f"{'experiment' if 'experiment' in combined else 'missing-evidence'}"
        )
        return ModelResponse(
            message=Message(role="assistant", content=final_text),
            content=final_text,
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


def test_validate_supported_python_fails_fast_for_old_versions():
    try:
        validate_supported_python((3, 9))
    except RuntimeError as exc:
        message = str(exc)
        assert "environment_error" in message
        assert "Python 3.10+" in message
        assert "py -3.13" in message
    else:
        raise AssertionError("Expected unsupported Python validation to fail fast.")


def test_multiturn_constraints_are_retained_across_rounds():
    asyncio.run(_test_multiturn_constraints_are_retained_across_rounds())


async def _test_multiturn_constraints_are_retained_across_rounds():
    runtime = Runtime(model=ConstraintTrackingModel(), memory=MemoryManager())
    agent = Agent(runtime=runtime)

    await agent.run("Round 1: keep codename Aurora-17 unchanged and keep the report under 800 words.", thread_id="multiturn-constraints")
    await agent.run("Round 2: every section must cite at least one concrete experiment type.", thread_id="multiturn-constraints")
    result = await agent.run("Round 3: produce the final coordination plan and preserve all prior constraints.", thread_id="multiturn-constraints")

    assert "Aurora-17" in result.output_text
    assert "800 words" in result.output_text
    assert "experiment" in result.output_text


def test_deprecated_collective_memory_is_not_reused_by_default():
    asyncio.run(_test_deprecated_collective_memory_is_not_reused_by_default())


async def _test_deprecated_collective_memory_is_not_reused_by_default():
    memory = MemoryManager()
    record_id = await memory.promote_collective_memory(
        thread_id="stale-thread",
        kind="policy",
        content="stale-omega should no longer be reused",
        tags=["stale"],
        source_agents=["reviewer"],
        confidence=0.9,
        scope="planning",
    )
    await memory.deprecate_collective_memory(record_id)

    assert await memory.search_collective_memory(query="stale-omega", thread_id="stale-thread") == []
