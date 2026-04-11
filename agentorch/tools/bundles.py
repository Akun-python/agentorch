from __future__ import annotations

from pathlib import Path

from agentorch.sandbox import SandboxManager, SandboxPolicy

from .execution import register_execution_tools
from .filesystem import register_filesystem_tools
from .git_tools import register_git_tools
from .web import register_web_tools


def register_default_agent_tools(
    registry,
    *,
    workspace_root: str | Path,
    sandbox: SandboxManager | None = None,
    execution_policy: SandboxPolicy | None = None,
    include_filesystem: bool = True,
    include_execution: bool = True,
    include_git: bool = True,
    include_web: bool = False,
    brave_api_key: str | None = None,
) -> None:
    if include_filesystem:
        register_filesystem_tools(registry, workspace_root)
    if include_execution and sandbox is not None:
        register_execution_tools(registry, sandbox, policy=execution_policy)
    if include_git:
        register_git_tools(registry, workspace_root)
    if include_web:
        register_web_tools(registry, brave_api_key=brave_api_key)
