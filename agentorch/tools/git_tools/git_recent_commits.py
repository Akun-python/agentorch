from __future__ import annotations

import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from agentorch.tools.base import FunctionTool, ToolError
from agentorch.tools.common import resolve_workspace_path


class GitRecentCommitsInput(BaseModel):
    path: str | None = Field(default=None, description="Optional repository path relative to the workspace root.")
    limit: int = Field(default=5, ge=1, le=50, description="Maximum number of commits to return.")


def create_git_recent_commits_tool(workspace_root: str | Path, *, name: str = "git_recent_commits") -> FunctionTool:
    root = Path(workspace_root).resolve()

    async def git_recent_commits(input: GitRecentCommitsInput):
        target = resolve_workspace_path(root, input.path, tool_name=name)
        command = ["git", "log", f"-{input.limit}", "--pretty=format:%H%x1f%an%x1f%ad%x1f%s", "--date=iso-strict"]
        try:
            completed = subprocess.run(
                command,
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
            raise ToolError(completed.stderr.strip() or "git log failed.", tool_name=name)
        commits = []
        for line in completed.stdout.splitlines():
            if not line.strip():
                continue
            commit_hash, author, authored_at, subject = line.split("\x1f", maxsplit=3)
            commits.append(
                {
                    "commit": commit_hash,
                    "author": author,
                    "authored_at": authored_at,
                    "subject": subject,
                }
            )
        return {
            "path": target.relative_to(root).as_posix() if target != root else ".",
            "commits": commits,
            "summary": f"Loaded {len(commits)} recent commit(s) from {target.relative_to(root).as_posix() if target != root else '.'}.",
        }

    return FunctionTool(
        name=name,
        description="Return recent commits for a git repository in structured form.",
        input_model=GitRecentCommitsInput,
        func=git_recent_commits,
        risk_level="low",
    )
