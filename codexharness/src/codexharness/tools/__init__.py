from __future__ import annotations

from ..bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from agentorch import ToolRegistry

from ..review_tools import ReviewCollector, create_collect_task_artifacts_tool
from .codex_tools import build_codex_tools
from .workspace_tools import build_workspace_tools


def build_tool_registry(*, workspace_manager, session_manager, review_collector: ReviewCollector) -> ToolRegistry:
    registry = ToolRegistry()
    for item in build_workspace_tools(workspace_manager):
        registry.register(item)
    for item in build_codex_tools(session_manager):
        registry.register(item)
    registry.register(create_collect_task_artifacts_tool(review_collector))
    return registry
