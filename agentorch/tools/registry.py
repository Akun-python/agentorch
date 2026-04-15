from __future__ import annotations

import inspect
from typing import Any
from pathlib import Path

from pydantic import ValidationError

from .base import BaseTool, ToolError, ToolResult


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    @classmethod
    def empty(cls) -> "ToolRegistry":
        return cls()

    @classmethod
    def from_tools(cls, *tools: BaseTool) -> "ToolRegistry":
        registry = cls()
        for tool in tools:
            registry.register(tool)
        return registry

    @classmethod
    def with_bundles(
        cls,
        *,
        workspace_root: str | Path,
        sandbox: Any | None = None,
        include_filesystem: bool = True,
        include_execution: bool = True,
        include_git: bool = True,
        include_web: bool = False,
        brave_api_key: str | None = None,
    ) -> "ToolRegistry":
        from .bundles import register_default_agent_tools

        registry = cls()
        register_default_agent_tools(
            registry,
            workspace_root=workspace_root,
            sandbox=sandbox,
            include_filesystem=include_filesystem,
            include_execution=include_execution,
            include_git=include_git,
            include_web=include_web,
            brave_api_key=brave_api_key,
        )
        return registry

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.spec.name] = tool

    def register_many(self, *tools: BaseTool) -> "ToolRegistry":
        for tool in tools:
            self.register(tool)
        return self

    def extend(self, other: "ToolRegistry") -> "ToolRegistry":
        for tool in other._tools.values():
            self.register(tool)
        return self

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise ToolError(f"Tool '{name}' is not registered.", tool_name=name)
        return self._tools[name]

    def list_specs(self) -> list[dict[str, Any]]:
        return [tool.to_openai_tool() for tool in self._tools.values()]

    async def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        tool = self.get(name)
        try:
            input_data = tool.input_model.model_validate(arguments)
        except ValidationError as exc:
            raise ToolError(f"Invalid tool arguments for '{name}': {exc}", tool_name=name) from exc
        return await tool.run(input_data)

    async def aclose(self) -> None:
        for tool in self._tools.values():
            close_async = getattr(tool, "aclose", None)
            if callable(close_async):
                outcome = close_async()
                if inspect.isawaitable(outcome):
                    await outcome

    def close(self) -> None:
        for tool in self._tools.values():
            close_sync = getattr(tool, "close", None)
            if callable(close_sync):
                close_sync()

    def __contains__(self, name: str) -> bool:
        return name in self._tools
