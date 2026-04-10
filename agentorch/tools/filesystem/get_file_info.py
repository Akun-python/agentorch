from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from agentorch.tools.base import FunctionTool, ToolError
from agentorch.tools.common import is_probably_binary, resolve_workspace_path


class GetFileInfoInput(BaseModel):
    path: str = Field(description="File or directory path relative to the workspace root.")


def _to_iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def create_get_file_info_tool(workspace_root: str | Path, *, name: str = "get_file_info") -> FunctionTool:
    root = Path(workspace_root).resolve()

    async def get_file_info(input: GetFileInfoInput):
        target = resolve_workspace_path(root, input.path, tool_name=name)
        if not target.exists():
            raise ToolError(f"Path '{target}' does not exist.", tool_name=name)
        stat = target.stat()
        is_file = target.is_file()
        return {
            "path": target.relative_to(root).as_posix(),
            "name": target.name,
            "type": "file" if is_file else "directory",
            "size_bytes": stat.st_size,
            "modified_at": _to_iso(stat.st_mtime),
            "created_at": _to_iso(stat.st_ctime),
            "is_binary": is_probably_binary(target) if is_file else False,
        }

    return FunctionTool(
        name=name,
        description="Return metadata for a workspace file or directory.",
        input_model=GetFileInfoInput,
        func=get_file_info,
        risk_level="low",
    )
