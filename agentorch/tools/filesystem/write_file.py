from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from agentorch.tools.base import FunctionTool, ToolError
from agentorch.tools.common import atomic_write_text, create_backup_file, ensure_parent_directory, resolve_workspace_path


class WriteFileInput(BaseModel):
    path: str = Field(description="File path relative to the workspace root.")
    content: str = Field(description="Full file content to write.")
    encoding: str = Field(default="utf-8", description="Text encoding used to write the file.")
    make_dirs: bool = Field(default=True, description="Whether to create parent directories when missing.")
    overwrite: bool = Field(default=True, description="Whether an existing file may be overwritten.")
    atomic: bool = Field(default=True, description="Whether to use an atomic temp-file replace strategy.")
    create_backup: bool = Field(default=False, description="Whether to create a .bak backup before overwriting an existing file.")


def create_write_file_tool(workspace_root: str | Path, *, name: str = "write_file") -> FunctionTool:
    root = Path(workspace_root).resolve()

    async def write_file(input: WriteFileInput):
        target = resolve_workspace_path(root, input.path, tool_name=name)
        ensure_parent_directory(target, make_dirs=input.make_dirs, tool_name=name)
        existed = target.exists()
        if existed and target.is_dir():
            raise ToolError(f"Path '{target}' is a directory, not a file.", tool_name=name)
        if existed and not input.overwrite:
            raise ToolError(f"File '{target}' already exists and overwrite is disabled.", tool_name=name)
        backup_path = create_backup_file(target, root=root, tool_name=name) if input.create_backup else None
        if input.atomic:
            atomic_write_text(target, input.content, encoding=input.encoding)
        else:
            target.write_text(input.content, encoding=input.encoding)
        return {
            "path": target.relative_to(root).as_posix(),
            "bytes_written": len(input.content.encode(input.encoding)),
            "characters_written": len(input.content),
            "created": not existed,
            "backup_path": backup_path,
        }

    return FunctionTool(
        name=name,
        description="Write full text content to a workspace file. Creates directories when requested.",
        input_model=WriteFileInput,
        func=write_file,
        risk_level="medium",
    )
