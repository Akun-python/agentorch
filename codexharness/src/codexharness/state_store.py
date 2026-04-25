from __future__ import annotations

import json
from pathlib import Path

from .config import HarnessConfig
from .schemas import CodexSessionEvent, CodexSessionState, HarnessRunState


class StateStore:
    def __init__(self, config: HarnessConfig) -> None:
        self.config = config
        self.config.ensure_runtime_layout()

    def _run_root(self, run_id: str) -> Path:
        path = self.config.state_root / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _run_state_path(self, run_id: str) -> Path:
        return self._run_root(run_id) / "run_state.json"

    def session_state_path(self, session_id: str) -> Path:
        return self.config.session_root / f"{session_id}.json"

    def session_log_path(self, session_id: str) -> Path:
        return self.config.log_root / f"{session_id}.jsonl"

    def artifact_path(self, task_id: str) -> Path:
        return self.config.artifact_root / f"{task_id}.json"

    def checkpoint_path(self, run_id: str, round_index: int) -> Path:
        target_root = self.config.checkpoint_root / run_id
        target_root.mkdir(parents=True, exist_ok=True)
        return target_root / f"round-{round_index:03d}.json"

    def list_run_ids(self) -> list[str]:
        if not self.config.state_root.exists():
            return []
        runs = [path.name for path in self.config.state_root.iterdir() if path.is_dir()]
        runs.sort()
        return runs

    def latest_run_id(self) -> str | None:
        runs: list[tuple[float, str]] = []
        if not self.config.state_root.exists():
            return None
        for path in self.config.state_root.iterdir():
            if not path.is_dir():
                continue
            state_path = path / "run_state.json"
            if state_path.exists():
                runs.append((state_path.stat().st_mtime, path.name))
        if not runs:
            return None
        runs.sort()
        return runs[-1][1]

    def save_run_state(self, state: HarnessRunState) -> Path:
        state.touch()
        path = self._run_state_path(state.run_id)
        path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load_run_state(self, run_id: str) -> HarnessRunState:
        path = self._run_state_path(run_id)
        return HarnessRunState.model_validate_json(path.read_text(encoding="utf-8"))

    def load_latest_run_state(self) -> HarnessRunState | None:
        run_id = self.latest_run_id()
        if run_id is None:
            return None
        return self.load_run_state(run_id)

    def write_checkpoint(self, state: HarnessRunState) -> Path:
        state.touch()
        path = self.checkpoint_path(state.run_id, state.round_index)
        path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        return path

    def list_checkpoints(self, run_id: str) -> list[Path]:
        target_root = self.config.checkpoint_root / run_id
        if not target_root.exists():
            return []
        checkpoints = [path for path in target_root.iterdir() if path.is_file() and path.suffix == ".json"]
        checkpoints.sort()
        return checkpoints

    def load_latest_checkpoint(self, run_id: str) -> HarnessRunState | None:
        checkpoints = self.list_checkpoints(run_id)
        if not checkpoints:
            return None
        path = checkpoints[-1]
        return HarnessRunState.model_validate_json(path.read_text(encoding="utf-8"))

    def save_session_state(self, session: CodexSessionState) -> Path:
        path = self.session_state_path(session.session_id)
        path.write_text(session.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load_session_state(self, session_id: str) -> CodexSessionState:
        path = self.session_state_path(session_id)
        return CodexSessionState.model_validate_json(path.read_text(encoding="utf-8"))

    def append_session_event(self, event: CodexSessionEvent) -> None:
        path = self.session_log_path(event.session_id)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False) + "\n")

    def load_session_events(self, session_id: str, *, after_event_index: int = 0) -> list[CodexSessionEvent]:
        path = self.session_log_path(session_id)
        if not path.exists():
            return []
        events: list[CodexSessionEvent] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                event = CodexSessionEvent.model_validate(payload)
                if event.event_index > after_event_index:
                    events.append(event)
        return events
