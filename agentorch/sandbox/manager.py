from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class ExecutionRequest(BaseModel):
    argv: list[str] = Field(default_factory=list)
    shell: bool = False
    workdir: str | Path | None = None
    env_overrides: dict[str, str] = Field(default_factory=dict)
    logical_executable: str | None = None

    @classmethod
    def from_command(
        cls,
        command: str | list[str] | tuple[str, ...],
        *,
        shell: bool = False,
        workdir: str | Path | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> "ExecutionRequest":
        logical_executable: str | None = None
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
            if sys.platform.startswith("win") and argv:
                command_text = command
                logical_executable = argv[0]
                executable_name = Path(argv[0]).name
                if shutil.which(executable_name) is None and executable_name.lower() in {"echo", "dir", "copy", "move", "type", "set", "cls"}:
                    comspec = os.environ.get("ComSpec") or os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "cmd.exe")
                    argv = [comspec, "/d", "/c", command_text]
        else:
            argv = [str(item) for item in command]
            if sys.platform.startswith("win") and argv:
                logical_executable = argv[0]
                executable_name = Path(argv[0]).name
                if shutil.which(executable_name) is None and executable_name.lower() in {"echo", "dir", "copy", "move", "type", "set", "cls"}:
                    command_text = subprocess.list2cmdline(argv)
                    comspec = os.environ.get("ComSpec") or os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "cmd.exe")
                    argv = [comspec, "/d", "/c", command_text]
        return cls(
            argv=argv,
            shell=shell,
            workdir=workdir,
            env_overrides=dict(env_overrides or {}),
            logical_executable=logical_executable,
        )


class ExecutionResult(BaseModel):
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration: float = 0.0
    argv: list[str] = Field(default_factory=list)
    shell: bool = False
    session_id: str | None = None
    persistent: bool = False
    result_repr: str | None = None
    workdir: str | None = None


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
        logical = request.logical_executable or request.argv[0]
        candidates = {
            executable,
            Path(request.argv[0]).name.lower(),
            Path(request.argv[0]).stem.lower(),
            str(logical).lower(),
            Path(str(logical)).name.lower(),
            Path(str(logical)).stem.lower(),
        }
        allowlist = [item.lower() for item in self.command_allowlist]
        blocklist = [item.lower() for item in self.command_blocklist]
        if allowlist and candidates.isdisjoint(allowlist):
            raise PermissionError(f"Command '{request.argv[0]}' is not allowlisted.")
        if not candidates.isdisjoint(blocklist):
            raise PermissionError(f"Command '{request.argv[0]}' is blocklisted.")
        return request


class SandboxSession(BaseModel):
    session_id: str
    policy: SandboxPolicy
    mode: Literal["python"] = "python"
    workdir: str | None = None


@dataclass
class _PythonSessionHandle:
    session: SandboxSession
    process: subprocess.Popen[str]
    workdir: Path
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


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
        request = ExecutionRequest(argv=[sys.executable, "-c", code], shell=False, workdir=workdir, logical_executable="python")
        return await self.run_command(request, policy=policy)

    async def create_python_session(self, *, policy: SandboxPolicy, workdir: str | Path) -> subprocess.Popen[str]:
        safe_workdir = policy.validate_workdir(workdir)
        worker_script = Path(__file__).with_name("python_worker.py")
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env.setdefault("PYTHONUTF8", "1")
        process = await asyncio.to_thread(
            subprocess.Popen,
            [sys.executable, "-u", str(worker_script)],
            cwd=str(safe_workdir),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if process.stdin is None or process.stdout is None or process.stderr is None:
            raise RuntimeError("Failed to create persistent python session pipes.")
        return process

    async def _communicate_python_session(
        self,
        process: subprocess.Popen[str],
        payload: dict[str, Any],
        *,
        timeout: float,
    ) -> dict[str, Any]:
        if process.stdin is None or process.stdout is None or process.stderr is None:
            raise RuntimeError("Persistent python session is missing stdin/stdout pipes.")

        def _write_request() -> None:
            process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            process.stdin.flush()

        await asyncio.wait_for(asyncio.to_thread(_write_request), timeout=timeout)

        try:
            raw_response = await asyncio.wait_for(asyncio.to_thread(process.stdout.readline), timeout=timeout)
        except asyncio.TimeoutError as exc:
            with contextlib.suppress(Exception):
                process.kill()
            raise TimeoutError(f"Persistent python session timed out after {timeout} seconds.") from exc

        if not raw_response:
            stderr = await asyncio.to_thread(process.stderr.read)
            raise RuntimeError(
                "Persistent python session terminated unexpectedly."
                + (f" Worker stderr: {stderr.strip()}" if stderr.strip() else "")
            )
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError as exc:
            stderr = await asyncio.to_thread(process.stderr.read)
            raise RuntimeError(
                "Persistent python session produced an invalid response."
                + (f" Worker stderr: {stderr.strip()}" if stderr.strip() else "")
            ) from exc

    async def run_python_session(
        self,
        process: subprocess.Popen[str],
        code: str,
        *,
        policy: SandboxPolicy,
        workdir: str | Path | None = None,
        session_id: str,
    ) -> ExecutionResult:
        safe_workdir = policy.validate_workdir(workdir).as_posix() if workdir is not None else None
        started = time.perf_counter()
        response = await self._communicate_python_session(
            process,
            {"action": "exec", "code": code, "workdir": safe_workdir},
            timeout=policy.timeout,
        )
        return ExecutionResult(
            stdout=str(response.get("stdout") or ""),
            stderr=str(response.get("stderr") or ""),
            exit_code=int(response.get("exit_code", 1)),
            duration=time.perf_counter() - started,
            argv=[sys.executable, "-c", code],
            shell=False,
            session_id=session_id,
            persistent=True,
            result_repr=response.get("result_repr"),
            workdir=response.get("workdir"),
        )

    async def reset_python_session(
        self,
        process: subprocess.Popen[str],
        *,
        policy: SandboxPolicy,
        workdir: str | Path,
    ) -> None:
        safe_workdir = policy.validate_workdir(workdir).as_posix()
        response = await self._communicate_python_session(
            process,
            {"action": "reset", "workdir": safe_workdir},
            timeout=policy.timeout,
        )
        if int(response.get("exit_code", 1)) != 0:
            raise RuntimeError(str(response.get("stderr") or "Failed to reset persistent python session."))

    async def close_python_session(self, process: subprocess.Popen[str], *, timeout: float) -> None:
        if process.poll() is not None:
            return
        with contextlib.suppress(Exception):
            await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: (
                        process.stdin.write(json.dumps({"action": "close"}, ensure_ascii=False) + "\n"),
                        process.stdin.flush(),
                    )
                ),
                timeout=timeout,
            )
        with contextlib.suppress(Exception):
            await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=timeout)
            return
        with contextlib.suppress(Exception):
            process.terminate()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=max(timeout / 2.0, 1.0))
            return
        with contextlib.suppress(Exception):
            process.kill()
            await asyncio.to_thread(process.wait)


class SandboxManager:
    def __init__(self, backend: LocalSubprocessSandbox | None = None, policy: SandboxPolicy | None = None) -> None:
        self.backend = backend or LocalSubprocessSandbox()
        self.policy = policy or SandboxPolicy()
        self._python_sessions: dict[str, _PythonSessionHandle] = {}

    async def create_session(
        self,
        policy: SandboxPolicy | None = None,
        *,
        mode: Literal["python"] = "python",
        workdir: str | Path | None = None,
    ) -> SandboxSession:
        effective_policy = policy or self.policy
        if mode != "python":
            raise NotImplementedError(f"Unsupported sandbox session mode: {mode}")
        safe_workdir = effective_policy.validate_workdir(workdir)
        session = SandboxSession(
            session_id=str(uuid.uuid4()),
            policy=effective_policy,
            mode=mode,
            workdir=safe_workdir.as_posix(),
        )
        process = await self.backend.create_python_session(policy=effective_policy, workdir=safe_workdir)
        self._python_sessions[session.session_id] = _PythonSessionHandle(session=session, process=process, workdir=safe_workdir)
        return session

    def list_sessions(self, *, mode: Literal["python"] | None = None) -> list[SandboxSession]:
        sessions = [handle.session for handle in self._python_sessions.values()]
        if mode is None:
            return sessions
        return [session for session in sessions if session.mode == mode]

    async def reset_session(self, session_id: str) -> SandboxSession:
        try:
            handle = self._python_sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"Unknown sandbox session: {session_id}") from exc
        async with handle.lock:
            await self.backend.reset_python_session(
                handle.process,
                policy=handle.session.policy,
                workdir=handle.workdir,
            )
        return handle.session

    async def close_session(self, session_id: str) -> None:
        try:
            handle = self._python_sessions.pop(session_id)
        except KeyError as exc:
            raise KeyError(f"Unknown sandbox session: {session_id}") from exc
        async with handle.lock:
            await self.backend.close_python_session(handle.process, timeout=handle.session.policy.timeout)

    async def aclose(self) -> None:
        for session_id in list(self._python_sessions.keys()):
            with contextlib.suppress(Exception):
                await self.close_session(session_id)

    def close(self) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.aclose())
            return
        raise RuntimeError(
            "SandboxManager.close() cannot be used inside a running event loop. "
            "Use 'await SandboxManager.aclose()' in notebooks and async applications."
        )

    async def execute(
        self,
        mode: Literal["shell", "python"],
        payload: str | list[str] | tuple[str, ...],
        *,
        workdir: str | Path | None = None,
        policy: SandboxPolicy | None = None,
        use_shell: bool = False,
        env_overrides: dict[str, str] | None = None,
        session_id: str | None = None,
    ) -> ExecutionResult:
        effective_policy = policy or self.policy
        if mode == "python":
            if session_id is not None:
                try:
                    handle = self._python_sessions[session_id]
                except KeyError as exc:
                    raise KeyError(f"Unknown sandbox session: {session_id}") from exc
                async with handle.lock:
                    return await self.backend.run_python_session(
                        handle.process,
                        str(payload),
                        policy=handle.session.policy,
                        workdir=workdir or handle.workdir,
                        session_id=session_id,
                    )
            return await self.backend.run_python(str(payload), policy=effective_policy, workdir=workdir)
        if session_id is not None:
            raise ValueError("Shell execution does not support persistent sandbox sessions.")
        request = ExecutionRequest.from_command(payload, shell=use_shell, workdir=workdir, env_overrides=env_overrides)
        return await self.backend.run_command(request, policy=effective_policy)
