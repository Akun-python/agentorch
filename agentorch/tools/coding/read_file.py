from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from agentorch.tools.base import FunctionTool, ToolError

from .common import resolve_workspace_path


class ReadFileInput(BaseModel):
    path: str = Field(description="File path relative to the workspace root.")
    start_line: int = Field(default=1, ge=1, description="1-based starting line number.")
    max_lines: int = Field(default=200, ge=1, le=2000, description="Maximum number of lines to read.")
    encoding: str = Field(default="utf-8", description="Text encoding used to read the file.")


def create_read_file_tool(workspace_root: str | Path, *, name: str = "read_file") -> FunctionTool:
    root = Path(workspace_root).resolve()

    async def read_file(input: ReadFileInput):
        target = resolve_workspace_path(root, input.path, tool_name=name)
        if not target.exists():
            raise ToolError(f"File '{target}' does not exist.", tool_name=name)
        if not target.is_file():
            raise ToolError(f"Path '{target}' is not a file.", tool_name=name)
        lines = target.read_text(encoding=input.encoding).splitlines()
        start_index = input.start_line - 1
        selected = lines[start_index : start_index + input.max_lines]
        return {
            "path": target.relative_to(root).as_posix(),
            "start_line": input.start_line,
            "end_line": input.start_line + max(len(selected) - 1, 0),
            "content": "\n".join(selected),
            "line_count": len(lines),
        }

    return FunctionTool(
        name=name,
        description="Read a text file from the workspace with optional line slicing.",
        input_model=ReadFileInput,
        func=read_file,
        risk_level="low",
    )
