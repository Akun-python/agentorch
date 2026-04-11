from __future__ import annotations

from pathlib import Path

from .git_diff_summary import create_git_diff_summary_tool
from .git_recent_commits import create_git_recent_commits_tool
from .git_status import create_git_status_tool


def register_git_tools(registry, workspace_root: str | Path) -> None:
    registry.register(create_git_status_tool(workspace_root))
    registry.register(create_git_diff_summary_tool(workspace_root))
    registry.register(create_git_recent_commits_tool(workspace_root))
