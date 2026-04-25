from __future__ import annotations

import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from agentorch.tools.base import FunctionTool, ToolError
from agentorch.tools.common import resolve_workspace_path


class GitStatusInput(BaseModel):
    path: str | None = Field(default=None, description="Optional repository path relative to the workspace root.")
    include_branch: bool = Field(default=True, description="Whether to include current branch information.")


def create_git_status_tool(workspace_root: str | Path, *, name: str = "git_status") -> FunctionTool:
    root = Path(workspace_root).resolve()

    async def git_status(input: GitStatusInput):
        target = resolve_workspace_path(root, input.path, tool_name=name)
        try:
            completed = subprocess.run(
                ["git", "status", "--short"],
                cwd=str(target),
                shell=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ToolError("Git is not installed or not available on PATH.", tool_name=name) from exc
        if completed.returncode != 0:
            raise ToolError(completed.stderr.strip() or "git status failed.", tool_name=name)
        branch = None
        if input.include_branch:
            branch_completed = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(target),
                shell=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
            if branch_completed.returncode == 0:
                branch = branch_completed.stdout.strip()
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        return {
            "path": target.relative_to(root).as_posix() if target != root else ".",
            "entries": lines,
            "clean": len(lines) == 0,
            "branch": branch,
            "summary": f"Git status for {target.relative_to(root).as_posix() if target != root else '.'}: {'clean' if len(lines) == 0 else f'{len(lines)} change(s)'}",
        }

    return FunctionTool(
        name=name,
        description="Return a concise git status summary for the workspace or a repository subdirectory.",
        input_model=GitStatusInput,
        func=git_status,
        risk_level="low",
    )
