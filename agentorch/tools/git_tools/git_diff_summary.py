from __future__ import annotations

import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from agentorch.tools.base import FunctionTool, ToolError
from agentorch.tools.common import resolve_workspace_path


class GitDiffSummaryInput(BaseModel):
    path: str | None = Field(default=None, description="Optional repository path relative to the workspace root.")
    staged: bool = Field(default=False, description="Whether to summarize staged changes instead of working tree changes.")
    target_ref: str | None = Field(default=None, description="Optional ref, commit, or revision range to diff against.")


def create_git_diff_summary_tool(workspace_root: str | Path, *, name: str = "git_diff_summary") -> FunctionTool:
    root = Path(workspace_root).resolve()

    async def git_diff_summary(input: GitDiffSummaryInput):
        target = resolve_workspace_path(root, input.path, tool_name=name)
        command = ["git", "diff", "--stat"]
        if input.staged:
            command.append("--cached")
        if input.target_ref:
            command.append(input.target_ref)
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
            raise ToolError(completed.stderr.strip() or "git diff --stat failed.", tool_name=name)
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        summary_line = lines[-1] if lines else ""
        return {
            "path": target.relative_to(root).as_posix() if target != root else ".",
            "staged": input.staged,
            "target_ref": input.target_ref,
            "lines": lines,
            "summary": summary_line,
            "detail_summary": f"Git diff summary for {target.relative_to(root).as_posix() if target != root else '.'} returned {len(lines)} line(s).",
        }

    return FunctionTool(
        name=name,
        description="Return a git diff --stat style summary for workspace changes.",
        input_model=GitDiffSummaryInput,
        func=git_diff_summary,
        risk_level="low",
    )
