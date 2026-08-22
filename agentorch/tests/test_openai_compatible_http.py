from __future__ import annotations

import asyncio
import json

import httpx

from agentorch.core import Message, ModelRequest
from agentorch.models.openai_compatible_http import OpenAICompatibleHTTPModel


def _request_model(transport: httpx.MockTransport) -> OpenAICompatibleHTTPModel:
    client = httpx.AsyncClient(transport=transport)
    return OpenAICompatibleHTTPModel(
        model="test-model",
        api_key="sk-test-only",
        base_url="https://provider.example/v1",
        client=client,
        max_retries=0,
    )


def test_http_adapter_normalizes_optional_response_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://provider.example/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer sk-test-only"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": None, "tool_calls": []},
                    }
                ]
            },
        )

    async def scenario() -> None:
        model = _request_model(httpx.MockTransport(handler))
        response = await model.generate(ModelRequest(messages=[Message(role="user", content="hi")]))
        assert response.content == ""
        assert response.usage.total_tokens == 0
        await model.aclose()

    asyncio.run(scenario())


def test_http_adapter_stream_ignores_role_and_usage_only_chunks() -> None:
    events = [
        {"choices": [{"delta": {"role": "assistant"}, "finish_reason": None}]},
        {"choices": [{"delta": {"content": "hello"}, "finish_reason": None}]},
        {"choices": [], "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream"] is True
        body = "".join(f"data: {json.dumps(event)}\n\n" for event in events) + "data: [DONE]\n\n"
        return httpx.Response(200, content=body.encode(), headers={"Content-Type": "text/event-stream"})

    async def scenario() -> None:
        model = _request_model(httpx.MockTransport(handler))
        chunks = [chunk async for chunk in model.stream(ModelRequest(messages=[Message(role="user", content="hi")]))]
        assert [chunk.delta_text for chunk in chunks] == ["", "hello", ""]
        assert chunks[-1].usage.total_tokens == 3
        await model.aclose()

    asyncio.run(scenario())


def test_http_adapter_stream_merges_tool_call_fragments_and_reasoning() -> None:
    events = [
        {
            "choices": [
                {
                    "delta": {
                        "reasoning_content": "先判断",
                        "tool_calls": [{"index": 0, "id": "call_1", "function": {"name": "lookup", "arguments": "{\"q\":"}}],
                    },
                    "finish_reason": None,
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {"tool_calls": [{"index": 0, "function": {"arguments": "\"agentorch\"}"}}]},
                    "finish_reason": "tool_calls",
                }
            ]
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        body = "".join(f"data: {json.dumps(event)}\n\n" for event in events) + "data: [DONE]\n\n"
        return httpx.Response(200, content=body.encode(), headers={"Content-Type": "text/event-stream"})

    async def scenario() -> None:
        model = _request_model(httpx.MockTransport(handler))
        chunks = [chunk async for chunk in model.stream(ModelRequest(messages=[Message(role="user", content="hi")]))]
        assert chunks[0].reasoning_delta_text == "先判断"
        assert chunks[0].tool_calls[0].arguments == {}
        assert chunks[1].tool_calls[0].arguments == {"q": "agentorch"}
        assert chunks[1].finish_reason == "tool_calls"
        await model.aclose()

    asyncio.run(scenario())


def test_http_adapter_surfaces_non_success_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "unauthorized"}})

    async def scenario() -> None:
        model = _request_model(httpx.MockTransport(handler))
        try:
            await model.generate(ModelRequest(messages=[Message(role="user", content="hi")]))
        except httpx.HTTPStatusError as exc:
            assert exc.response.status_code == 401
        else:  # pragma: no cover
            raise AssertionError("expected HTTPStatusError")
        await model.aclose()

    asyncio.run(scenario())
