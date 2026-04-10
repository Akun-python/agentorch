from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, Field

from agentorch.config.settings import _get_brave_api_key

from ..base import FunctionTool, ToolError


class BraveSearchInput(BaseModel):
    query: str
    count: int = Field(default=5, ge=1, le=20)
    country: str | None = None
    search_lang: str | None = None
    safesearch: str = Field(default="moderate", pattern="^(strict|moderate|off)$")
    freshness: str | None = None
    spellcheck: bool = True


def _normalize_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("web", {}).get("results", []) or []
    normalized: list[dict[str, Any]] = []
    for item in items:
        normalized.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "description": item.get("description"),
                "age": item.get("age"),
                "language": item.get("language"),
                "family_friendly": item.get("family_friendly"),
                "type": item.get("type"),
            }
        )
    return normalized


def create_brave_search_tool(
    *,
    api_key: str | None = None,
    name: str = "brave_search",
    base_url: str = "https://api.search.brave.com/res/v1/web/search",
    timeout: float = 60.0,
    client: httpx.AsyncClient | None = None,
) -> FunctionTool:
    def _format_http_error(exc: httpx.HTTPError) -> str:
        error_type = type(exc).__name__
        message = str(exc).strip() or repr(exc)
        if isinstance(exc, httpx.ConnectTimeout):
            return (
                f"{error_type}: unable to connect to Brave Search within {timeout} seconds. "
                "This usually indicates network connectivity restrictions, proxy issues, or Brave endpoint reachability problems. "
                f"Original error: {message}"
            )
        if isinstance(exc, httpx.ReadTimeout):
            return (
                f"{error_type}: Brave Search did not return a response within {timeout} seconds. "
                f"Original error: {message}"
            )
        if isinstance(exc, httpx.ConnectError):
            return (
                f"{error_type}: connection to Brave Search could not be established. "
                "Check network access, proxy configuration, and firewall settings. "
                f"Original error: {message}"
            )
        return f"{error_type}: {message}"

    async def brave_search(input: BraveSearchInput):
        token = api_key or _get_brave_api_key()
        if not token:
            raise ToolError(
                "Brave Search API key is missing. Set BRAVE_SEARCH_API_KEY or BRAVE_API_KEY, or pass api_key explicitly.",
                tool_name=name,
            )

        params = {
            "q": input.query,
            "count": input.count,
            "safesearch": input.safesearch,
            "spellcheck": int(input.spellcheck),
        }
        if input.country:
            params["country"] = input.country
        if input.search_lang:
            params["search_lang"] = input.search_lang
        if input.freshness:
            params["freshness"] = input.freshness

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": token,
        }

        owns_client = client is None
        selected_client = client or httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=timeout))
        try:
            response = await selected_client.get(base_url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
            return {
                "query": input.query,
                "results": _normalize_results(payload),
                "total_results": len(payload.get("web", {}).get("results", []) or []),
                "raw": payload,
            }
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip() if exc.response is not None else str(exc)
            raise ToolError(f"Brave Search request failed: {detail}", tool_name=name) from exc
        except httpx.HTTPError as exc:
            raise ToolError(f"Brave Search request failed: {_format_http_error(exc)}", tool_name=name) from exc
        finally:
            if owns_client:
                await selected_client.aclose()

    return FunctionTool(
        name=name,
        description="Search the public web through Brave Search API and return structured search results.",
        input_model=BraveSearchInput,
        func=brave_search,
        risk_level="medium",
        timeout=timeout,
        retryable=True,
    )
