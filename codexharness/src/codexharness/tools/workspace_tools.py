from __future__ import annotations

from pydantic import BaseModel, Field

from ..bootstrap import ensure_repo_root_on_path
from ..schemas import WorkspaceMode

ensure_repo_root_on_path()

from agentorch import tool


class PrepareTaskWorkspaceInput(BaseModel):
    task_id: str
    mode: WorkspaceMode = WorkspaceMode.SHARED
    write_scope: list[str] = Field(default_factory=list)


def build_workspace_tools(workspace_manager) -> list:
    @tool(description="Prepare a shared, copy-based, or git-worktree workspace for a Codex task.")
    async def prepare_task_workspace(input: PrepareTaskWorkspaceInput):
        allocation = await workspace_manager.prepare(
            task_id=input.task_id,
            mode=input.mode,
            write_scope=input.write_scope,
        )
        return allocation.model_dump(mode="json")

    return [prepare_task_workspace]
