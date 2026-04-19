from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from pydantic import BaseModel

from .bootstrap import ensure_repo_root_on_path
from .config import HarnessConfig
from .schemas import HarnessTask, TaskArtifactBundle
from .state_store import StateStore

ensure_repo_root_on_path()

from agentorch import tool


class CollectTaskArtifactsInput(BaseModel):
    task_id: str
    workspace_path: str
    session_id: str | None = None


class ReviewCollector:
    def __init__(self, config: HarnessConfig, state_store: StateStore) -> None:
        self.config = config
        self.state_store = state_store

    async def collect(self, task: HarnessTask) -> TaskArtifactBundle:
        workspace = task.workspace_path or str(self.config.project_root)
        baseline = task.metadata.get("workspace_baseline")
        current_snapshot = await self.capture_baseline(workspace)
        changed_files = self._delta_changed_files(baseline, current_snapshot)
        diff_summary = await self._git_diff_stat(workspace, paths=changed_files)
        last_message = ""
        log_excerpt = ""
        if task.assigned_session_id:
            session = self.state_store.load_session_state(task.assigned_session_id)
            events = self.state_store.load_session_events(task.assigned_session_id)
            last_message = session.last_message or ""
            log_excerpt = "\n".join(item.raw_text for item in events[-20:])
        bundle = TaskArtifactBundle(
            task_id=task.task_id,
            workspace_path=workspace,
            changed_files=changed_files,
            git_diff_summary=diff_summary,
            last_agent_message=last_message,
            log_excerpt=log_excerpt,
            metadata={
                "baseline_changed_files": sorted((baseline or {}).get("changed_files", [])) if isinstance(baseline, dict) else [],
                "current_changed_files": current_snapshot["changed_files"],
            },
        )
        self.state_store.artifact_path(task.task_id).write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
        return bundle

    async def capture_baseline(self, workspace: str) -> dict[str, object]:
        changed_files = await self._git_status_paths(workspace)
        fingerprints = {
            path: self._fingerprint(Path(workspace) / path)
            for path in changed_files
        }
        return {
            "changed_files": changed_files,
            "fingerprints": fingerprints,
        }

    async def _git_diff_stat(self, workspace: str, *, paths: list[str] | None = None) -> str:
        args = ["diff", "--stat"]
        if paths:
            args.append("--")
            args.extend(paths)
        return await self._run_git(workspace, *args)

    async def _git_status_paths(self, workspace: str) -> list[str]:
        stdout = await self._run_git(workspace, "status", "--porcelain=v1", "--untracked-files=all")
        paths: list[str] = []
        for line in stdout.splitlines():
            if len(line) < 4:
                continue
            entry = line[3:].strip()
            if not entry:
                continue
            if " -> " in entry:
                entry = entry.split(" -> ", 1)[1].strip()
            paths.append(entry)
        return sorted(dict.fromkeys(paths))

    def _delta_changed_files(self, baseline: object, current_snapshot: dict[str, object]) -> list[str]:
        current_changed = current_snapshot.get("changed_files")
        current_fingerprints = current_snapshot.get("fingerprints")
        if not isinstance(current_changed, list) or not isinstance(current_fingerprints, dict):
            return []
        if not isinstance(baseline, dict):
            return list(current_changed)
        baseline_fingerprints = baseline.get("fingerprints")
        if not isinstance(baseline_fingerprints, dict):
            return list(current_changed)
        delta: list[str] = []
        for path in current_changed:
            if not isinstance(path, str):
                continue
            if baseline_fingerprints.get(path) != current_fingerprints.get(path):
                delta.append(path)
        return delta

    async def _run_git(self, workspace: str, *args: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            workspace,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return ""
        return stdout.decode("utf-8", "replace").strip()

    def _fingerprint(self, path: Path) -> str | None:
        if not path.exists() or not path.is_file():
            return None
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()


def create_collect_task_artifacts_tool(collector: ReviewCollector):
    @tool(description="Collect changed files, diff summary, and recent Codex output for a task.")
    async def collect_task_artifacts(input: CollectTaskArtifactsInput):
        task = HarnessTask(
            task_id=input.task_id,
            goal="collect-artifacts",
            workspace_path=input.workspace_path,
            assigned_session_id=input.session_id,
        )
        bundle = await collector.collect(task)
        return bundle.model_dump(mode="json")

    return collect_task_artifacts
