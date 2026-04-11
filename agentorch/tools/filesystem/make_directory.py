from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from agentorch.tools.base import FunctionTool, ToolError
from agentorch.tools.common import resolve_workspace_path


class MakeDirectoryInput(BaseModel):
    path: str = Field(description="Directory path relative to the workspace root.")
    parents: bool = Field(default=True, description="Whether to create missing parent directories.")
    exist_ok: bool = Field(default=True, description="Whether an existing directory should be treated as success.")


def create_make_directory_tool(workspace_root: str | Path, *, name: str = "make_directory") -> FunctionTool:
    root = Path(workspace_root).resolve()

    async def make_directory(input: MakeDirectoryInput):
        target = resolve_workspace_path(root, input.path, tool_name=name)
        if target.exists() and not target.is_dir():
            raise ToolError(f"Path '{target}' already exists and is not a directory.", tool_name=name)
        existed = target.exists()
        target.mkdir(parents=input.parents, exist_ok=input.exist_ok)
        return {
            "path": target.relative_to(root).as_posix(),
            "created": not existed,
        }

    return FunctionTool(
        name=name,
        description="Create a directory inside the workspace.",
        input_model=MakeDirectoryInput,
        func=make_directory,
        risk_level="low",
    )
