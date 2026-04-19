from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from .config import HarnessConfig
from .schemas import WorkspaceAllocation, WorkspaceMode


class WorkspaceManager:
    def __init__(self, config: HarnessConfig) -> None:
        self.config = config
        self.config.ensure_runtime_layout()

    async def prepare(self, *, task_id: str, mode: WorkspaceMode | str, write_scope: list[str] | None = None) -> WorkspaceAllocation:
        resolved_mode = WorkspaceMode(mode)
        if resolved_mode == WorkspaceMode.SHARED:
            return WorkspaceAllocation(
                task_id=task_id,
                workspace_path=str(self.config.project_root),
                workspace_kind=resolved_mode,
            )
        if resolved_mode == WorkspaceMode.COPY:
            return await self._prepare_copy(task_id=task_id, write_scope=write_scope or [])
        return await self._prepare_git_worktree(task_id=task_id, write_scope=write_scope or [])

    async def _prepare_copy(self, *, task_id: str, write_scope: list[str]) -> WorkspaceAllocation:
        target = self.config.worktree_root / task_id
        if not target.exists():
            await asyncio.to_thread(
                shutil.copytree,
                self.config.project_root,
                target,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".mypy_cache"),
            )
        return WorkspaceAllocation(
            task_id=task_id,
            workspace_path=str(target),
            workspace_kind=WorkspaceMode.COPY,
            metadata={"write_scope": write_scope},
        )

    async def _prepare_git_worktree(self, *, task_id: str, write_scope: list[str]) -> WorkspaceAllocation:
        target = self.config.worktree_root / task_id
        branch_name = self._branch_name(task_id)
        if target.exists():
            return WorkspaceAllocation(
                task_id=task_id,
                workspace_path=str(target),
                workspace_kind=WorkspaceMode.GIT_WORKTREE,
                branch_name=branch_name,
                metadata={"write_scope": write_scope, "reused": True},
            )
        is_repo = await self._is_git_repo(self.config.project_root)
        if not is_repo:
            return await self._prepare_copy(task_id=task_id, write_scope=write_scope)
        branch_exists = await self._branch_exists(self.config.project_root, branch_name)
        command = [
            "git",
            "-C",
            str(self.config.project_root),
            "worktree",
            "add",
        ]
        if not branch_exists:
            command.extend(["-b", branch_name])
        else:
            command.extend(["--force"])
        command.extend([str(target), branch_name if branch_exists else "HEAD"])
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, _ = await proc.communicate()
        if proc.returncode != 0:
            return await self._prepare_copy(task_id=task_id, write_scope=write_scope)
        return WorkspaceAllocation(
            task_id=task_id,
            workspace_path=str(target),
            workspace_kind=WorkspaceMode.GIT_WORKTREE,
            branch_name=branch_name,
            metadata={"write_scope": write_scope},
        )

    async def _is_git_repo(self, path: Path) -> bool:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(path),
            "rev-parse",
            "--is-inside-work-tree",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return proc.returncode == 0 and stdout.decode("utf-8", "replace").strip() == "true"

    async def _branch_exists(self, path: Path, branch_name: str) -> bool:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(path),
            "show-ref",
            "--verify",
            "--quiet",
            f"refs/heads/{branch_name}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0

    def _branch_name(self, task_id: str) -> str:
        safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in task_id).strip("-")
        return f"codexharness/{safe or 'task'}"
