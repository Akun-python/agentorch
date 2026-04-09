import asyncio

import pytest
from pydantic import BaseModel

from agentorch.tools import ToolRegistry, tool
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
