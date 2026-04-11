from __future__ import annotations

from agentorch.core import Message, ModelRequest, ModelResponse, ToolCall, UsageInfo
from agentorch.models.base import BaseModelAdapter


class MockEchoModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        user_message = next((item.content for item in reversed(request.messages) if item.role == "user"), "")
        return ModelResponse(
            message=Message(role="assistant", content=f"Echo: {user_message}"),
            content=f"Echo: {user_message}",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=12),
        )


class MockToolModel(BaseModelAdapter):
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        if self.calls == 1 and request.tools:
            preferred_tool = request.tools[0]["function"]["name"]
            return ModelResponse(
                message=Message(
                    role="assistant",
                    content="",
                    tool_calls=[ToolCall(id="tool-call-1", name=preferred_tool, arguments={"query": "agentorch experiments"})],
                ),
                content="",
                tool_calls=[ToolCall(id="tool-call-1", name=preferred_tool, arguments={"query": "agentorch experiments"})],
                finish_reason="tool_calls",
                usage=UsageInfo(total_tokens=21),
            )
        return ModelResponse(
            message=Message(role="assistant", content="Completed with tool evidence."),
            content="Completed with tool evidence.",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=13),
        )


class MockFailureModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        raise RuntimeError("intentional experiment failure")


class MockJudgeModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content='{"score": 1.0, "reason": "mock judge"}'),
            content='{"score": 1.0, "reason": "mock judge"}',
            finish_reason="stop",
            usage=UsageInfo(total_tokens=8),
        )


class MockStrongModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        user_message = next((item.content for item in reversed(request.messages) if item.role == "user"), "")
        return ModelResponse(
            message=Message(role="assistant", content=f"Strong response: {user_message}"),
            content=f"Strong response: {user_message}",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=28),
        )


class MockBalancedModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        user_message = next((item.content for item in reversed(request.messages) if item.role == "user"), "")
        return ModelResponse(
            message=Message(role="assistant", content=f"Balanced response: {user_message}"),
            content=f"Balanced response: {user_message}",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=20),
        )


class MockWeakModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        user_message = next((item.content for item in reversed(request.messages) if item.role == "user"), "")
        truncated = user_message.split(".")[0]
        return ModelResponse(
            message=Message(role="assistant", content=f"Weak response: {truncated}"),
            content=f"Weak response: {truncated}",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=14),
        )
