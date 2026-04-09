from __future__ import annotations

import asyncio
import shlex
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ExecutionResult(BaseModel):
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration: float = 0.0


class SandboxPolicy(BaseModel):
    allowed_paths: list[Path] = Field(default_factory=lambda: [Path.cwd()])
    timeout: float = 30.0
    command_allowlist: list[str] = Field(default_factory=list)
    command_blocklist: list[str] = Field(default_factory=list)

    def validate_workdir(self, workdir: str | Path | None) -> Path:
        target = Path(workdir or Path.cwd()).resolve()
        if not any(str(target).startswith(str(path.resolve())) for path in self.allowed_paths):
            raise PermissionError(f"Workdir '{target}' is outside the allowed sandbox paths.")
        return target

    def validate_command(self, command: str) -> None:
        head = shlex.split(command)[0] if command else ""
        if self.command_allowlist and head not in self.command_allowlist:
            raise PermissionError(f"Command '{head}' is not allowlisted.")
        if self.command_blocklist and head in self.command_blocklist:
            raise PermissionError(f"Command '{head}' is blocklisted.")


class SandboxSession(BaseModel):
    session_id: str
    policy: SandboxPolicy


class LocalSubprocessSandbox:
    async def run_shell(self, command: str, *, policy: SandboxPolicy, workdir: str | Path | None = None) -> ExecutionResult:
        policy.validate_command(command)
        safe_workdir = policy.validate_workdir(workdir)
        started = time.perf_counter()

        try:
            completed = await asyncio.to_thread(
                subprocess.run,
                command,
                cwd=str(safe_workdir),
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=policy.timeout,
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Sandbox command timed out after {policy.timeout} seconds.")
        return ExecutionResult(
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
            duration=time.perf_counter() - started,
        )

    async def run_python(self, code: str, *, policy: SandboxPolicy, workdir: str | Path | None = None) -> ExecutionResult:
        policy.validate_command("python")
        safe_workdir = policy.validate_workdir(workdir)
        started = time.perf_counter()
        try:
            completed = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, "-c", code],
                cwd=str(safe_workdir),
                shell=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=policy.timeout,
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Sandbox command timed out after {policy.timeout} seconds.")
        return ExecutionResult(
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
            duration=time.perf_counter() - started,
        )


class SandboxManager:
    def __init__(self, backend: LocalSubprocessSandbox | None = None, policy: SandboxPolicy | None = None) -> None:
        self.backend = backend or LocalSubprocessSandbox()
        self.policy = policy or SandboxPolicy()

    async def create_session(self, policy: SandboxPolicy | None = None) -> SandboxSession:
        return SandboxSession(session_id=str(uuid.uuid4()), policy=policy or self.policy)

    async def execute(
        self,
        mode: Literal["shell", "python"],
        payload: str,
        *,
        workdir: str | Path | None = None,
        policy: SandboxPolicy | None = None,
    ) -> ExecutionResult:
        effective_policy = policy or self.policy
        if mode == "shell":
            return await self.backend.run_shell(payload, policy=effective_policy, workdir=workdir)
        if mode == "python":
            return await self.backend.run_python(payload, policy=effective_policy, workdir=workdir)
        raise ValueError(f"Unsupported sandbox mode: {mode}")
