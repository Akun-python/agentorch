from __future__ import annotations

import fnmatch
from pathlib import Path

from pydantic import BaseModel, Field

from agentorch.tools.base import FunctionTool, ToolError

from .common import is_hidden_path, resolve_workspace_path


class FindFilesInput(BaseModel):
    pattern: str = Field(description="Glob pattern used to match file names, for example '*.py'.")
    path: str | None = Field(default=None, description="Optional directory path relative to the workspace root.")
    max_results: int = Field(default=200, ge=1, le=5000, description="Maximum number of file paths to return.")
    include_hidden: bool = Field(default=False, description="Whether to include hidden files and directories.")


def create_find_files_tool(workspace_root: str | Path, *, name: str = "find_files") -> FunctionTool:
    root = Path(workspace_root).resolve()

    async def find_files(input: FindFilesInput):
        base = resolve_workspace_path(root, input.path, tool_name=name)
        if not base.exists():
            raise ToolError(f"Search path '{base}' does not exist.", tool_name=name)
        iterator = [base] if base.is_file() else base.rglob("*")
        matches = []
        for item in iterator:
            if not item.is_file():
                continue
            relative_path = item.relative_to(root)
            if not input.include_hidden and is_hidden_path(relative_path):
                continue
            relative_str = relative_path.as_posix()
            if fnmatch.fnmatch(item.name, input.pattern) or fnmatch.fnmatch(relative_str, input.pattern):
                matches.append(relative_str)
                if len(matches) >= input.max_results:
                    break
        return {"matches": matches}

    return FunctionTool(
        name=name,
        description="Find files in the workspace using glob-style matching.",
        input_model=FindFilesInput,
        func=find_files,
        risk_level="low",
    )
