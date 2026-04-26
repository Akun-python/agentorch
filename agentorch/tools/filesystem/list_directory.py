from __future__ import annotations

from heapq import nsmallest
from pathlib import Path

from pydantic import BaseModel, Field

from agentorch.tools.base import FunctionTool, ToolError
from agentorch.tools.common import is_hidden_path, resolve_workspace_path


class ListDirectoryInput(BaseModel):
    path: str | None = Field(default=None, description="Directory path relative to the workspace root.")
    recursive: bool = Field(default=False, description="Whether to recursively list nested files and directories.")
    include_hidden: bool = Field(default=False, description="Whether to include hidden files and directories.")
    max_entries: int = Field(default=200, ge=1, le=5000, description="Maximum number of entries to return.")
    include_size: bool = Field(default=False, description="Whether file sizes should be included in returned entries.")


def create_list_directory_tool(workspace_root: str | Path, *, name: str = "list_directory") -> FunctionTool:
    root = Path(workspace_root).resolve()

    async def list_directory(input: ListDirectoryInput):
        target = resolve_workspace_path(root, input.path, tool_name=name)
        if not target.exists():
            raise ToolError(f"Directory '{target}' does not exist.", tool_name=name)
        if not target.is_dir():
            raise ToolError(f"Path '{target}' is not a directory.", tool_name=name)
        iterator = target.rglob("*") if input.recursive else target.iterdir()

        def iter_candidates():
            for item in iterator:
                relative_path = item.relative_to(root)
                if not input.include_hidden and is_hidden_path(relative_path):
                    continue
                is_directory = item.is_dir()
                yield (not is_directory, relative_path.as_posix().lower()), relative_path, item, is_directory

        selected = nsmallest(input.max_entries, iter_candidates(), key=lambda payload: payload[0])
        entries = []
        for _, relative_path, item, is_directory in selected:
            entry = {"path": relative_path.as_posix(), "type": "directory" if is_directory else "file"}
            if input.include_size and not is_directory:
                entry["size_bytes"] = item.stat().st_size
            entries.append(entry)
        return {"workspace_root": root.as_posix(), "entries": entries, "count": len(entries)}

    return FunctionTool(
        name=name,
        description="List files and directories inside the workspace. Useful for codebase exploration.",
        input_model=ListDirectoryInput,
        func=list_directory,
        risk_level="low",
    )
