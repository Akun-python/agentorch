from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from agentorch.tools.base import FunctionTool, ToolError
from agentorch.tools.common import read_text_file, resolve_workspace_path


class ReadFileInput(BaseModel):
    path: str = Field(description="File path relative to the workspace root.")
    start_line: int = Field(default=1, ge=1, description="1-based starting line number.")
    max_lines: int = Field(default=200, ge=1, le=2000, description="Maximum number of lines to read.")
    encoding: str = Field(default="utf-8", description="Text encoding used to read the file.")
    include_line_numbers: bool = Field(default=False, description="Whether returned content should be prefixed with 1-based line numbers.")


def create_read_file_tool(workspace_root: str | Path, *, name: str = "read_file") -> FunctionTool:
    root = Path(workspace_root).resolve()

    async def read_file(input: ReadFileInput):
        target = resolve_workspace_path(root, input.path, tool_name=name)
        text = read_text_file(target, encoding=input.encoding, tool_name=name)
        lines = text.splitlines()
        start_index = input.start_line - 1
        if start_index > len(lines):
            raise ToolError(
                f"Start line {input.start_line} is beyond the end of '{target}' ({len(lines)} lines).",
                tool_name=name,
            )
        selected = lines[start_index : start_index + input.max_lines]
        rendered = "\n".join(
            f"{start_index + index + 1}: {line}" for index, line in enumerate(selected)
        ) if input.include_line_numbers else "\n".join(selected)
        return {
            "path": target.relative_to(root).as_posix(),
            "start_line": input.start_line,
            "end_line": input.start_line + max(len(selected) - 1, 0),
            "content": rendered,
            "line_count": len(lines),
            "truncated": start_index + len(selected) < len(lines),
            "summary": f"Read {len(selected)} line(s) from {target.relative_to(root).as_posix()} starting at line {input.start_line}.",
        }

    return FunctionTool(
        name=name,
        description="Read a text file from the workspace with optional line slicing.",
        input_model=ReadFileInput,
        func=read_file,
        risk_level="low",
    )
