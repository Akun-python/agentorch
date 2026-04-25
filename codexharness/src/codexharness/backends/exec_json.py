from __future__ import annotations

import asyncio
import json
import os
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..config import HarnessConfig
from ..schemas import (
    CodexSessionEvent,
    CodexSessionState,
    PollSessionResult,
    SessionStatus,
    StartCodexTaskRequest,
    utc_now,
)
from ..state_store import StateStore


class ExecJsonBackend:
    def __init__(self, config: HarnessConfig, state_store: StateStore) -> None:
        self.config = config
        self.state_store = state_store
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._stream_tasks: dict[str, list[asyncio.Task[None]]] = {}
        self._watch_tasks: dict[str, asyncio.Task[None]] = {}

    async def start(self, request: StartCodexTaskRequest) -> CodexSessionState:
        command = self._build_start_command(request)
        return await self._spawn_session(
            task_id=request.task_id,
            cwd=request.cwd,
            command=command,
        )

    async def resume(self, *, previous_session: CodexSessionState, prompt: str) -> CodexSessionState:
        if not previous_session.codex_thread_id:
            return await self.start(
                StartCodexTaskRequest(
                    task_id=previous_session.task_id,
                    cwd=previous_session.cwd,
                    prompt=prompt,
                    sandbox_mode=self.config.codex_sandbox,
                    approval_policy=self.config.codex_approval,
                    skip_git_repo_check=self.config.codex_skip_git_repo_check,
                )
            )
        command = self._build_resume_command(previous_session, prompt)
        return await self._spawn_session(
            task_id=previous_session.task_id,
            cwd=previous_session.cwd,
            command=command,
            resumed_from_session_id=previous_session.session_id,
        )

    async def poll(self, session_id: str, *, after_event_index: int = 0) -> PollSessionResult:
        session = self.state_store.load_session_state(session_id)
        events = self.state_store.load_session_events(session_id, after_event_index=after_event_index)
        return PollSessionResult(session=session, events=events, next_offset=session.event_count)

    async def wait(self, session_id: str, *, timeout: float | None = None) -> CodexSessionState:
        process = self._processes.get(session_id)
        if process is not None and process.returncode is None:
            if timeout is None:
                await process.wait()
            else:
                await asyncio.wait_for(process.wait(), timeout=timeout)
        watch_task = self._watch_tasks.get(session_id)
        if watch_task is not None:
            await asyncio.gather(watch_task, return_exceptions=True)
        return self.state_store.load_session_state(session_id)

    async def stop(self, session_id: str) -> CodexSessionState:
        process = self._processes.get(session_id)
        if process is not None and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except TimeoutError:
                process.kill()
                await process.wait()
        session = self.state_store.load_session_state(session_id)
        session.status = SessionStatus.STOPPED
        session.finished_at = utc_now()
        self.state_store.save_session_state(session)
        await self._append_system_event(session_id, {"event": "session_stopped"})
        return session

    async def restore(self, session_id: str) -> CodexSessionState:
        return self.state_store.load_session_state(session_id)

    def _build_start_command(self, request: StartCodexTaskRequest) -> list[str]:
        command = self._build_codex_command_prefix()
        if request.approval_policy:
            command.extend(["-a", request.approval_policy])
        command.extend(
            [
                "exec",
                "--json",
                "-C",
                request.cwd,
                "-s",
                request.sandbox_mode,
            ]
        )
        if request.skip_git_repo_check:
            command.append("--skip-git-repo-check")
        command.append(request.prompt)
        return command

    def _build_resume_command(self, previous_session: CodexSessionState, prompt: str) -> list[str]:
        command = self._build_codex_command_prefix()
        if self.config.codex_approval:
            command.extend(["-a", self.config.codex_approval])
        command.extend(["-C", previous_session.cwd, "exec", "resume", "--json"])
        if self.config.codex_skip_git_repo_check:
            command.append("--skip-git-repo-check")
        command.extend([previous_session.codex_thread_id or "--last", prompt])
        return command

    def _build_codex_command_prefix(self) -> list[str]:
        command = [self.config.codex_binary]
        if self.config.codex_model_name:
            command.extend(["-m", self.config.codex_model_name])
        command.extend(self._build_provider_overrides())
        return command

    def _build_provider_overrides(self) -> list[str]:
        if not self.config.codex_base_url:
            return []
        provider_id = "codexharness_proxy"
        overrides = [
            f"model_provider={json.dumps(provider_id)}",
            f"model_providers.{provider_id}.name={json.dumps('CodexHarness Proxy')}",
            f"model_providers.{provider_id}.base_url={json.dumps(self.config.codex_base_url)}",
            f"model_providers.{provider_id}.wire_api={json.dumps('responses')}",
        ]
        if self.config.codex_api_key:
            overrides.append(f"model_providers.{provider_id}.env_key={json.dumps('CODEXHARNESS_CODEX_API_KEY')}")
        return [item for override in overrides for item in ("-c", override)]

    def _build_process_env(self) -> dict[str, str]:
        env = os.environ.copy()
        if self.config.codex_api_key:
            env["OPENAI_API_KEY"] = self.config.codex_api_key
            env["CODEXHARNESS_CODEX_API_KEY"] = self.config.codex_api_key
        return env

    async def _spawn_session(
        self,
        *,
        task_id: str,
        cwd: str,
        command: list[str],
        resumed_from_session_id: str | None = None,
    ) -> CodexSessionState:
        resolved_cwd = Path(cwd).resolve()
        if not resolved_cwd.exists():
            raise FileNotFoundError(f"Codex child task cwd does not exist: {resolved_cwd}")
        command = command.copy()
        command[0] = self._resolve_executable(command[0])
        session_id = f"session-{uuid4().hex[:12]}"
        log_path = self.state_store.session_log_path(session_id)
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(resolved_cwd),
            env=self._build_process_env(),
        )
        session = CodexSessionState(
            session_id=session_id,
            task_id=task_id,
            cwd=str(resolved_cwd),
            resumed_from_session_id=resumed_from_session_id,
            status=SessionStatus.RUNNING,
            pid=process.pid,
            started_at=utc_now(),
            last_activity_at=utc_now(),
            log_path=str(log_path),
        )
        self._processes[session_id] = process
        self.state_store.save_session_state(session)
        await self._append_system_event(session_id, {"event": "session_started", "argv": command})
        self._stream_tasks[session_id] = [
            asyncio.create_task(self._consume_stream(session_id, process.stdout, "stdout")),
            asyncio.create_task(self._consume_stream(session_id, process.stderr, "stderr")),
        ]
        self._watch_tasks[session_id] = asyncio.create_task(self._watch_process(session_id, process))
        return session

    def _resolve_executable(self, executable: str) -> str:
        candidate = Path(executable)
        if candidate.parent != Path(".") or candidate.suffix:
            if candidate.exists():
                return str(candidate)
            raise FileNotFoundError(f"Configured codex binary was not found: {executable}")
        resolved = shutil.which(executable) or shutil.which(f"{executable}.cmd") or shutil.which(f"{executable}.exe")
        if resolved:
            return resolved
        if os.name == "nt" and executable.lower() == "codex":
            appdata = os.environ.get("APPDATA")
            if appdata:
                npm_cmd = Path(appdata) / "npm" / "codex.cmd"
                if npm_cmd.exists():
                    return str(npm_cmd)
        raise FileNotFoundError(
            f"Could not resolve executable '{executable}'. "
            "Pass --codex-binary with a full path, for example C:\\Users\\<user>\\AppData\\Roaming\\npm\\codex.cmd."
        )

    async def _consume_stream(
        self,
        session_id: str,
        stream: asyncio.StreamReader | None,
        channel: str,
    ) -> None:
        if stream is None:
            return
        while True:
            chunk = await stream.readline()
            if not chunk:
                break
            text = chunk.decode("utf-8", "replace").rstrip("\r\n")
            parsed = self._parse_line(text)
            await self._append_event(session_id, stream=channel, raw_text=text, parsed=parsed)

    async def _watch_process(self, session_id: str, process: asyncio.subprocess.Process) -> None:
        await process.wait()
        stream_tasks = self._stream_tasks.pop(session_id, [])
        if stream_tasks:
            await asyncio.gather(*stream_tasks, return_exceptions=True)
        async with self._locks[session_id]:
            session = self.state_store.load_session_state(session_id)
            session.exit_code = process.returncode
            session.finished_at = utc_now()
            session.last_activity_at = utc_now()
            session.status = SessionStatus.FINISHED if process.returncode == 0 else SessionStatus.ERRORED
            if process.returncode not in (0, None):
                session.error_message = f"Codex exited with code {process.returncode}"
            self.state_store.save_session_state(session)
        await self._append_system_event(session_id, {"event": "session_finished", "exit_code": process.returncode})
        self._processes.pop(session_id, None)
        self._watch_tasks.pop(session_id, None)

    async def _append_system_event(self, session_id: str, payload: dict[str, Any]) -> None:
        await self._append_event(session_id, stream="system", raw_text=json.dumps(payload, ensure_ascii=False), parsed=payload)

    async def _append_event(self, session_id: str, *, stream: str, raw_text: str, parsed: dict[str, Any]) -> None:
        async with self._locks[session_id]:
            session = self.state_store.load_session_state(session_id)
            event = CodexSessionEvent(
                session_id=session_id,
                event_index=session.event_count + 1,
                stream=stream,  # type: ignore[arg-type]
                raw_text=raw_text,
                parsed=parsed,
            )
            session.event_count = event.event_index
            session.last_activity_at = event.created_at
            thread_id = self._extract_thread_id(parsed)
            if thread_id:
                session.codex_thread_id = thread_id
            extracted = self._extract_message(parsed, raw_text)
            if extracted:
                session.last_message = extracted
            self.state_store.append_session_event(event)
            self.state_store.save_session_state(session)

    def _parse_line(self, text: str) -> dict[str, Any]:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return {"unstructured_text": text}
        return payload if isinstance(payload, dict) else {"value": payload}

    def _extract_message(self, payload: Any, fallback: str) -> str | None:
        if isinstance(payload, dict):
            if "unstructured_text" in payload:
                return None
            if payload.get("type") == "item.completed":
                item = payload.get("item")
                if isinstance(item, dict) and item.get("type") == "agent_message":
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        return text.strip()
            for key in ("output_text", "text", "content", "message", "last_message", "summary"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            for value in payload.values():
                nested = self._extract_message(value, "")
                if nested:
                    return nested
        if isinstance(payload, list):
            for item in payload:
                nested = self._extract_message(item, "")
                if nested:
                    return nested
        return None

    def _extract_thread_id(self, payload: Any) -> str | None:
        if isinstance(payload, dict):
            thread_id = payload.get("thread_id")
            if isinstance(thread_id, str) and thread_id.strip():
                return thread_id.strip()
            for value in payload.values():
                nested = self._extract_thread_id(value)
                if nested:
                    return nested
        if isinstance(payload, list):
            for item in payload:
                nested = self._extract_thread_id(item)
                if nested:
                    return nested
        return None
