from __future__ import annotations

import httpx

from .brave_search import create_brave_search_tool


def register_web_tools(registry, *, brave_api_key: str | None = None, client: httpx.AsyncClient | None = None) -> None:
    registry.register(create_brave_search_tool(api_key=brave_api_key, client=client))
