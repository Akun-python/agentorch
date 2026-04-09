import asyncio
from pydantic import BaseModel

from agentorch.core import Message, ModelRequest, ModelResponse, ToolCall, UsageInfo
from agentorch.models.base import BaseModelAdapter
from agentorch.runtime import Agent, Runtime
from agentorch.tools import ToolRegistry, tool


class FakeModel(BaseModelAdapter):
    def __init__(self) -> None:
        self.calls = 0
        self.seen_requests: list[ModelRequest] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.seen_requests.append(request)
        self.calls += 1
        if self.calls == 1:
            return ModelResponse(
                message=Message(
                    role="assistant",
                    content="",
                    tool_calls=[ToolCall(id="call-1", name="lookup", arguments={"query": "weather"})],
                    metadata={},
                ),
                content="",
                tool_calls=[ToolCall(id="call-1", name="lookup", arguments={"query": "weather"})],
                finish_reason="tool_calls",
                usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            )
        return ModelResponse(
            message=Message(role="assistant", content="The weather is sunny."),
            content="The weather is sunny.",
            finish_reason="stop",
            usage=UsageInfo(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        )


class LookupInput(BaseModel):
    query: str


@tool(description="Return a fake lookup result.")
async def lookup(input: LookupInput):
    return {"query": input.query, "result": "sunny"}


def test_runtime_runs_model_tool_and_finish():
    asyncio.run(_test_runtime_runs_model_tool_and_finish())


async def _test_runtime_runs_model_tool_and_finish():
    model = FakeModel()
    tools = ToolRegistry()
    tools.register(lookup)
    runtime = Runtime(model=model, tools=tools)
    agent = Agent(runtime=runtime)
    result = await agent.run("what is the weather", thread_id="thread-1")
    assert result.output_text == "The weather is sunny."
    assert len(result.tool_results) == 1
    assert result.usage.total_tokens == 25
    second_request = model.seen_requests[1]
    assert len(second_request.messages) == 4
    assistant_messages = [message for message in second_request.messages if message.role == "assistant"]
    assert assistant_messages
    assert assistant_messages[-1].tool_calls[0].name == "lookup"
