from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from agentorch.tools.base import FunctionTool, ToolError
from agentorch.tools.common import (
    atomic_write_text,
    create_backup_file,
    ensure_parent_directory,
    read_text_file,
    resolve_workspace_path,
)


class AppendFileInput(BaseModel):
    path: str = Field(description="File path relative to the workspace root.")
    content: str = Field(description="Text to append to the file.")
    encoding: str = Field(default="utf-8", description="Text encoding used to write the file.")
    make_dirs: bool = Field(default=True, description="Whether to create parent directories when missing.")
    ensure_newline: bool = Field(default=False, description="Whether to prepend a newline when appending to a non-empty file.")
    atomic: bool = Field(default=True, description="Whether to use a read-modify-write atomic update.")
    create_backup: bool = Field(default=False, description="Whether to create a .bak backup before appending to an existing file.")


def create_append_file_tool(workspace_root: str | Path, *, name: str = "append_file") -> FunctionTool:
    root = Path(workspace_root).resolve()

    async def append_file(input: AppendFileInput):
        target = resolve_workspace_path(root, input.path, tool_name=name)
        ensure_parent_directory(target, make_dirs=input.make_dirs, tool_name=name)
        if target.exists() and target.is_dir():
            raise ToolError(f"Path '{target}' is a directory, not a file.", tool_name=name)
        existing = ""
        if target.exists():
            existing = read_text_file(target, encoding=input.encoding, tool_name=name)
        prefix = ""
        if input.ensure_newline and existing and not existing.endswith(("\n", "\r")):
            prefix = "\n"
        updated = f"{existing}{prefix}{input.content}"
        backup_path = create_backup_file(target, root=root, tool_name=name) if input.create_backup else None
        if input.atomic:
            atomic_write_text(target, updated, encoding=input.encoding)
        else:
            with target.open("a", encoding=input.encoding) as handle:
                handle.write(prefix + input.content)
        return {
            "path": target.relative_to(root).as_posix(),
            "appended_characters": len(prefix + input.content),
            "backup_path": backup_path,
        }

    return FunctionTool(
        name=name,
        description="Append text to a workspace file.",
        input_model=AppendFileInput,
        func=append_file,
        risk_level="medium",
    )
