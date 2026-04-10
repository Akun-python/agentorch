from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from agentorch.tools.base import FunctionTool, ToolError

from .common import resolve_workspace_path


class WriteFileInput(BaseModel):
    path: str = Field(description="File path relative to the workspace root.")
    content: str = Field(description="Full file content to write.")
    encoding: str = Field(default="utf-8", description="Text encoding used to write the file.")
    make_dirs: bool = Field(default=True, description="Whether to create parent directories when missing.")


def create_write_file_tool(workspace_root: str | Path, *, name: str = "write_file") -> FunctionTool:
    root = Path(workspace_root).resolve()

    async def write_file(input: WriteFileInput):
        target = resolve_workspace_path(root, input.path, tool_name=name)
        if input.make_dirs:
            target.parent.mkdir(parents=True, exist_ok=True)
        elif not target.parent.exists():
            raise ToolError(f"Parent directory '{target.parent}' does not exist.", tool_name=name)
        target.write_text(input.content, encoding=input.encoding)
        return {
            "path": target.relative_to(root).as_posix(),
            "bytes_written": len(input.content.encode(input.encoding)),
            "characters_written": len(input.content),
        }

    return FunctionTool(
        name=name,
        description="Write full text content to a workspace file. Creates directories when requested.",
        input_model=WriteFileInput,
        func=write_file,
        risk_level="medium",
    )
