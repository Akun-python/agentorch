from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel

from agentorch.tools import ToolRegistry, create_brave_search_tool, tool


class QueryInput(BaseModel):
    query: str


@tool(description="Return a deterministic local lookup result for experiments.")
async def local_lookup(input: QueryInput):
    return {"query": input.query, "result": "local lookup evidence for experiments"}


@tool(description="Return a deterministic long-horizon planning scaffold.")
async def plan_outline(input: QueryInput):
    return {
        "query": input.query,
        "steps": [
            "clarify task",
            "search evidence",
            "delegate subtasks",
            "synthesize final answer",
        ],
    }


def build_tool_registry(*, enable_live_web_search: bool) -> tuple[ToolRegistry, dict[str, Any]]:
    registry = ToolRegistry()
    registry.register(local_lookup)
    registry.register(plan_outline)

    live_web_available = False
    brave_key = os.getenv("BRAVE_SEARCH_API_KEY") or os.getenv("BRAVE_API_KEY")
    if enable_live_web_search and brave_key:
        registry.register(create_brave_search_tool(api_key=brave_key))
        live_web_available = True

    return registry, {
        "live_web_available": live_web_available,
        "registered_tools": [
            spec.get("function", {}).get("name") if isinstance(spec, dict) else spec.name
            for spec in registry.list_specs()
        ],
    }
