from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator


def _default_harness_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _first_nonempty_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is None:
            continue
        stripped = value.strip()
        if stripped:
            return stripped
    return None


def _env_int(default: int, *names: str) -> int:
    for name in names:
        value = os.getenv(name)
        if value is None:
            continue
        stripped = value.strip()
        if not stripped:
            continue
        try:
            return int(stripped)
        except ValueError:
            continue
    return default


def _env_float(default: float, *names: str) -> float:
    for name in names:
        value = os.getenv(name)
        if value is None:
            continue
        stripped = value.strip()
        if not stripped:
            continue
        try:
            return float(stripped)
        except ValueError:
            continue
    return default


class HarnessConfig(BaseModel):
    project_root: Path
    harness_root: Path = Field(default_factory=_default_harness_root)
    runtime_root: Path | None = None
    worktree_root: Path | None = None
    log_root: Path | None = None
    session_root: Path | None = None
    checkpoint_root: Path | None = None
    state_root: Path | None = None
    artifact_root: Path | None = None
    agentorch_runtime_root: Path | None = None
    model_name: str = Field(
        default_factory=lambda: _first_nonempty_env(
            "CODEXHARNESS_MODEL",
            "CODEXHARNESS_MODEL_NAME",
            "MODEL_NAME",
            "OPENAI_MODEL",
        )
        or "gpt-4.1-mini"
    )
    api_key: str | None = Field(default_factory=lambda: _first_nonempty_env("CODEXHARNESS_API_KEY", "OPENAI_API_KEY", "API_KEY"))
    base_url: str | None = Field(default_factory=lambda: _first_nonempty_env("CODEXHARNESS_BASE_URL", "OPENAI_BASE_URL", "BASE_URL"))
    codex_model_name: str | None = Field(
        default_factory=lambda: _first_nonempty_env(
            "CODEXHARNESS_CODEX_MODEL",
            "CODEXHARNESS_CODEX_MODEL_NAME",
        )
    )
    codex_api_key: str | None = Field(default_factory=lambda: _first_nonempty_env("CODEXHARNESS_CODEX_API_KEY"))
    codex_base_url: str | None = Field(default_factory=lambda: _first_nonempty_env("CODEXHARNESS_CODEX_BASE_URL"))
    model_timeout: float = Field(default_factory=lambda: _env_float(180.0, "CODEXHARNESS_MODEL_TIMEOUT"))
    model_max_retries: int = Field(default_factory=lambda: _env_int(6, "CODEXHARNESS_MODEL_MAX_RETRIES"))
    planner_max_tasks: int = 4
    max_rounds: int = 3
    max_parallel_tasks: int = 2
    max_task_retries: int = 1
    workspace_mode: Literal["shared", "git-worktree", "copy"] = "shared"
    codex_binary: str = Field(default_factory=lambda: os.getenv("CODEXHARNESS_CODEX_BIN", "codex"))
    codex_backend: Literal["exec_json"] = "exec_json"
    codex_sandbox: str = "workspace-write"
    codex_approval: str = "never"
    codex_skip_git_repo_check: bool = False
    enable_human_feedback: bool = True
    persist_thread_messages: bool = True
    thread_history_recall_limit: int = 6
    poll_interval_seconds: float = 0.75

    @model_validator(mode="after")
    def _resolve_paths(self) -> "HarnessConfig":
        self.project_root = self.project_root.resolve()
        self.harness_root = self.harness_root.resolve()
        self.runtime_root = (self.runtime_root or (self.harness_root / "runtime")).resolve()
        self.worktree_root = (self.worktree_root or (self.harness_root / "worktrees")).resolve()
        self.log_root = (self.log_root or (self.runtime_root / "logs")).resolve()
        self.session_root = (self.session_root or (self.runtime_root / "sessions")).resolve()
        self.checkpoint_root = (self.checkpoint_root or (self.runtime_root / "checkpoints")).resolve()
        self.state_root = (self.state_root or (self.runtime_root / "state")).resolve()
        self.artifact_root = (self.artifact_root or (self.runtime_root / "artifacts")).resolve()
        self.agentorch_runtime_root = (self.agentorch_runtime_root or (self.runtime_root / ".agentorch")).resolve()
        return self

    def ensure_runtime_layout(self) -> None:
        for path in (
            self.runtime_root,
            self.worktree_root,
            self.log_root,
            self.session_root,
            self.checkpoint_root,
            self.state_root,
            self.artifact_root,
            self.agentorch_runtime_root,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def validate_runtime_requirements(self) -> None:
        missing: list[str] = []
        if not (self.api_key or "").strip():
            missing.append("CODEXHARNESS_API_KEY or OPENAI_API_KEY")
        if not (self.base_url or "").strip():
            missing.append("CODEXHARNESS_BASE_URL or OPENAI_BASE_URL")
        if missing:
            joined = ", ".join(missing)
            raise ValueError(
                "codexharness supervisor model is not configured. "
                f"Set {joined}, or pass an env file with --env-file before using run/resume."
            )
