from __future__ import annotations

import asyncio
import shlex
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class ExecutionRequest(BaseModel):
    argv: list[str] = Field(default_factory=list)
    shell: bool = False
    workdir: str | Path | None = None
    env_overrides: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_command(
        cls,
        command: str | list[str] | tuple[str, ...],
        *,
        shell: bool = False,
        workdir: str | Path | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> "ExecutionRequest":
        if shell:
            if isinstance(command, str):
                command_text = command
            else:
                command_text = subprocess.list2cmdline([str(item) for item in command])
            if sys.platform.startswith("win"):
                argv = ["powershell", "-Command", command_text]
            else:
                argv = ["sh", "-lc", command_text]
        elif isinstance(command, str):
            argv = shlex.split(command, posix=False)
        else:
            argv = [str(item) for item in command]
        return cls(argv=argv, shell=shell, workdir=workdir, env_overrides=dict(env_overrides or {}))


class ExecutionResult(BaseModel):
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration: float = 0.0
    argv: list[str] = Field(default_factory=list)
    shell: bool = False


class SandboxPolicy(BaseModel):
    allowed_paths: list[Path] = Field(default_factory=list)
    timeout: float = 30.0
    command_allowlist: list[str] = Field(default_factory=list)
    command_blocklist: list[str] = Field(default_factory=list)
    allow_shell: bool = False

    def validate_workdir(self, workdir: str | Path | None) -> Path:
        if not self.allowed_paths:
            raise PermissionError("Sandbox has no allowed workdir roots configured.")
        target = Path(workdir or Path.cwd()).resolve()
        for path in self.allowed_paths:
            allowed = path.resolve()
            try:
                target.relative_to(allowed)
                return target
            except ValueError:
                continue
        raise PermissionError(f"Workdir '{target}' is outside the allowed sandbox paths.")

    def validate_command(self, request: ExecutionRequest) -> ExecutionRequest:
        if not request.argv:
            raise PermissionError("Sandbox command argv cannot be empty.")
        if request.shell and not self.allow_shell:
            raise PermissionError("Shell execution is disabled by sandbox policy.")
        executable = request.argv[0].lower()
        allowlist = [item.lower() for item in self.command_allowlist]
        blocklist = [item.lower() for item in self.command_blocklist]
        if allowlist and executable not in allowlist:
            raise PermissionError(f"Command '{request.argv[0]}' is not allowlisted.")
        if executable in blocklist:
            raise PermissionError(f"Command '{request.argv[0]}' is blocklisted.")
        return request


class SandboxSession(BaseModel):
    session_id: str
    policy: SandboxPolicy


class LocalSubprocessSandbox:
    async def run_command(self, request: ExecutionRequest, *, policy: SandboxPolicy) -> ExecutionResult:
        validated = policy.validate_command(request)
        safe_workdir = policy.validate_workdir(validated.workdir)
        started = time.perf_counter()
        try:
            completed = await asyncio.to_thread(
                subprocess.run,
                validated.argv,
                cwd=str(safe_workdir),
                shell=False,
                env=validated.env_overrides or None,
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
            argv=list(validated.argv),
            shell=validated.shell,
        )

    async def run_python(self, code: str, *, policy: SandboxPolicy, workdir: str | Path | None = None) -> ExecutionResult:
        request = ExecutionRequest(argv=[sys.executable, "-c", code], shell=False, workdir=workdir)
        return await self.run_command(request, policy=policy)


class SandboxManager:
    def __init__(self, backend: LocalSubprocessSandbox | None = None, policy: SandboxPolicy | None = None) -> None:
        self.backend = backend or LocalSubprocessSandbox()
        self.policy = policy or SandboxPolicy()

    async def create_session(self, policy: SandboxPolicy | None = None) -> SandboxSession:
        return SandboxSession(session_id=str(uuid.uuid4()), policy=policy or self.policy)

    async def execute(
        self,
        mode: Literal["shell", "python"],
        payload: str | list[str] | tuple[str, ...],
        *,
        workdir: str | Path | None = None,
        policy: SandboxPolicy | None = None,
        use_shell: bool = False,
        env_overrides: dict[str, str] | None = None,
    ) -> ExecutionResult:
        effective_policy = policy or self.policy
        if mode == "python":
            return await self.backend.run_python(str(payload), policy=effective_policy, workdir=workdir)
        request = ExecutionRequest.from_command(payload, shell=use_shell, workdir=workdir, env_overrides=env_overrides)
        return await self.backend.run_command(request, policy=effective_policy)
