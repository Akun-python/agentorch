from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from .base import BaseTool, ToolError, ToolResult


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.spec.name] = tool

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

    def __contains__(self, name: str) -> bool:
        return name in self._tools
