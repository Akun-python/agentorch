import asyncio

import pytest
from pydantic import BaseModel

import httpx

from agentorch.tools import ToolRegistry, create_brave_search_tool, tool
from agentorch.tools.base import ToolError


class AddInput(BaseModel):
    a: int
    b: int


@tool(description="Add two numbers.")
async def add(input: AddInput):
    return {"sum": input.a + input.b}


class SlowInput(BaseModel):
    delay: float


@tool(description="Sleep for a while.", timeout=0.01)
async def slow(input: SlowInput):
    await asyncio.sleep(input.delay)
    return {"done": True}


def test_tool_registry_executes_structured_tool():
    asyncio.run(_test_tool_registry_executes_structured_tool())


async def _test_tool_registry_executes_structured_tool():
    registry = ToolRegistry()
    registry.register(add)
    result = await registry.execute("add", {"a": 2, "b": 3})
    assert result.success is True
    assert result.data["sum"] == 5


def test_tool_timeout_is_wrapped():
    asyncio.run(_test_tool_timeout_is_wrapped())


async def _test_tool_timeout_is_wrapped():
    registry = ToolRegistry()
    registry.register(slow)
    with pytest.raises(ToolError):
        await registry.execute("slow", {"delay": 0.1})


def test_brave_search_tool_returns_normalized_results():
    asyncio.run(_test_brave_search_tool_returns_normalized_results())


async def _test_brave_search_tool_returns_normalized_results():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/res/v1/web/search"
        assert request.headers["X-Subscription-Token"] == "brave-test"
        assert request.url.params["q"] == "agentorch"
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "title": "agentorch docs",
                            "url": "https://example.com/agentorch",
                            "description": "Structured orchestration framework",
                            "language": "en",
                            "family_friendly": True,
                            "type": "search_result",
                        }
                    ]
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.search.brave.com")
    try:
        tool = create_brave_search_tool(api_key="brave-test", client=client)
        result = await tool.run(tool.input_model(query="agentorch"))
    finally:
        await client.aclose()

    assert result.success is True
    assert result.data["results"][0]["title"] == "agentorch docs"
    assert result.data["results"][0]["url"] == "https://example.com/agentorch"


def test_brave_search_tool_requires_api_key():
    asyncio.run(_test_brave_search_tool_requires_api_key())


async def _test_brave_search_tool_requires_api_key():
    tool = create_brave_search_tool(api_key=None)
    with pytest.raises(ToolError):
        await tool.run(tool.input_model(query="agentorch"))
