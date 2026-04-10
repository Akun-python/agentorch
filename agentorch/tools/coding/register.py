from __future__ import annotations

from agentorch.tools.filesystem import register_filesystem_tools


def register_coding_tools(registry, workspace_root) -> None:
    register_filesystem_tools(registry, workspace_root)
