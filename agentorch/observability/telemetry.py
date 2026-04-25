from __future__ import annotations

import json
import logging
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from agentorch.core import UsageInfo
from agentorch.security import PayloadBudgetConfig, RedactionConfig, sanitize_for_export, shape_payload


class EventBus:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append({"event_type": event_type, **payload})


class EventSink(ABC):
    @abstractmethod
    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError


class Logger:
    def __init__(
        self,
        name: str = "agentorch",
        file_path: str | Path | None = None,
        *,
        redaction: RedactionConfig | dict[str, object] | None = None,
        payload_budget: PayloadBudgetConfig | dict[str, object] | None = None,
    ) -> None:
        self.logger = logging.getLogger(name)
        self.redaction = RedactionConfig.from_any(redaction)
        self.payload_budget = PayloadBudgetConfig.from_any(payload_budget)
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(console_handler)
        if file_path:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(file_path, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(file_handler)

    def log(self, event_type: str, payload: dict[str, Any]) -> None:
        event_record = shape_payload({"event_type": event_type, **payload}, budget=self.payload_budget, redaction=self.redaction)
        self.logger.info(json.dumps(event_record, ensure_ascii=False))


class ConsoleEventSink(EventSink):
    IMPORTANT_EVENTS = {"final_result", "run_failed", "human_feedback_emitted", "run_completed"}

    def __init__(
        self,
        mode: Literal["silent", "important_only", "all"] = "silent",
        *,
        redaction: RedactionConfig | dict[str, object] | None = None,
        payload_budget: PayloadBudgetConfig | dict[str, object] | None = None,
    ) -> None:
        self.mode = mode
        self.redaction = RedactionConfig.from_any(redaction)
        self.payload_budget = PayloadBudgetConfig.from_any(payload_budget)
        self._logger = logging.getLogger("agentorch.console")
        self._logger.setLevel(logging.INFO)
        self._logger.handlers.clear()
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(handler)

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.mode == "silent":
            return
        if self.mode == "important_only" and event_type not in self.IMPORTANT_EVENTS:
            return
        event_record = shape_payload({"event_type": event_type, **payload}, budget=self.payload_budget, redaction=self.redaction)
        self._logger.info(json.dumps(event_record, ensure_ascii=False))


class TodoProjection:
    TERMINAL_STATUSES = {"completed", "failed", "cancelled", "waiting_human"}
    NOISY_EVENTS = {"prompt_built", "context_budget_reported", "budget_consumed", "memory_written"}

    def __init__(self, connection_factory) -> None:
        self._connection_factory = connection_factory

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _todo_key(event_type: str, payload: dict[str, Any]) -> str | None:
        task_id = payload.get("task_id") or "root"
        tool_name = payload.get("tool_name")
        agent_name = payload.get("agent_name")
        if event_type == "run_started" or event_type == "run_completed" or event_type == "run_failed":
            return "run:root"
        if event_type == "task_created":
            return f"task:{payload.get('task_id')}"
        if event_type.startswith("reasoning_"):
            return f"reasoning:{task_id}"
        if event_type.startswith("retrieval_"):
            return f"retrieval:{task_id}"
        if event_type in {"tool_called", "tool_result"} and tool_name:
            return f"tool:{task_id}:{tool_name}"
        if event_type in {"agent_delegated", "agent_completed"} and agent_name:
            return f"agent:{task_id}:{agent_name}"
        if event_type == "human_feedback_emitted":
            return f"human_feedback:{task_id}"
        return None

    @staticmethod
    def _category(event_type: str) -> str | None:
        if event_type in {"run_started", "run_completed", "run_failed"}:
            return "run"
        if event_type == "task_created":
            return "task"
        if event_type.startswith("reasoning_"):
            return "reasoning"
        if event_type.startswith("retrieval_"):
            return "retrieval"
        if event_type in {"tool_called", "tool_result"}:
            return "tool"
        if event_type in {"agent_delegated", "agent_completed"}:
            return "agent"
        if event_type == "human_feedback_emitted":
            return "human_feedback"
        return None

    @staticmethod
    def _title(event_type: str, payload: dict[str, Any]) -> str:
        if event_type in {"run_started", "run_completed", "run_failed"}:
            return f"Run {payload.get('run_id', '')}".strip()
        if event_type == "task_created":
            metadata = payload.get("metadata") or {}
            return str(metadata.get("goal") or f"Task {payload.get('task_id', '')}").strip()
        if event_type.startswith("reasoning_"):
            return "Reasoning"
        if event_type.startswith("retrieval_"):
            return "Retrieval"
        if event_type in {"tool_called", "tool_result"}:
            return f"Tool: {payload.get('tool_name', 'unknown')}"
        if event_type in {"agent_delegated", "agent_completed"}:
            return f"Agent: {payload.get('agent_name', 'unknown')}"
        if event_type == "human_feedback_emitted":
            return str(payload.get("title") or "Human Feedback")
        return event_type

    @staticmethod
    def _metadata(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "feedback_id",
            "kind",
            "severity",
            "blocking",
            "tool_call_id",
            "query",
            "visited_sources",
            "chunk_count",
            "status",
            "error_category",
            "error_stage",
            "prompt_char_estimate",
            "context_compaction_applied",
        )
        return {key: payload[key] for key in keys if key in payload}

    @classmethod
    def _status_for_event(cls, event_type: str, payload: dict[str, Any]) -> str | None:
        if event_type == "run_started":
            return "in_progress"
        if event_type == "task_created":
            return "in_progress"
        if event_type == "reasoning_started":
            return "in_progress"
        if event_type == "reasoning_completed":
            return "completed"
        if event_type == "retrieval_started":
            return "in_progress"
        if event_type == "retrieval_completed":
            return "completed"
        if event_type == "tool_called":
            return "in_progress"
        if event_type == "tool_result":
            return "failed" if payload.get("is_error") else "completed"
        if event_type == "agent_delegated":
            return "in_progress"
        if event_type == "agent_completed":
            raw_status = str(payload.get("status", "completed"))
            return "failed" if raw_status == "failed" else "completed"
        if event_type == "human_feedback_emitted":
            return "waiting_human"
        if event_type == "run_completed":
            raw_status = str(payload.get("status", "completed"))
            if raw_status in {"completed", "failed", "waiting_human"}:
                return raw_status
            return "completed"
        if event_type == "run_failed":
            return "failed"
        return None

    def apply(self, event_type: str, payload: dict[str, Any]) -> None:
        if event_type in self.NOISY_EVENTS:
            return
        todo_key = self._todo_key(event_type, payload)
        category = self._category(event_type)
        if todo_key is None or category is None:
            return
        run_id = str(payload.get("run_id") or "")
        thread_id = str(payload.get("thread_id") or "")
        if not run_id or not thread_id:
            return
        with self._connection_factory() as conn:
            self._upsert_todo(
                conn,
                run_id=run_id,
                thread_id=thread_id,
                todo_key=todo_key,
                category=category,
                title=self._title(event_type, payload),
                status=self._status_for_event(event_type, payload),
                event_type=event_type,
                payload=payload,
            )
            if event_type == "reasoning_step_started":
                self._update_reasoning_progress(conn, run_id=run_id, todo_key=todo_key, step_index=int(payload.get("step_index", 0)), completed=False)
            elif event_type == "reasoning_step_completed":
                self._update_reasoning_progress(conn, run_id=run_id, todo_key=todo_key, step_index=int(payload.get("step_index", 0)), completed=True)
            elif event_type == "run_completed":
                self._finalize_open_items(conn, run_id=run_id, root_status=str(payload.get("status", "completed")))
            elif event_type == "run_failed":
                self._fail_open_items(conn, run_id=run_id)

    def _upsert_todo(
        self,
        conn: sqlite3.Connection,
        *,
        run_id: str,
        thread_id: str,
        todo_key: str,
        category: str,
        title: str,
        status: str | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        now = self._utc_now()
        existing = conn.execute(
            "SELECT status, progress_current, progress_total, started_at, metadata_json FROM run_todos WHERE run_id = ? AND todo_key = ?",
            (run_id, todo_key),
        ).fetchone()
        task_id = payload.get("task_id")
        agent_name = payload.get("agent_name")
        metadata = self._metadata(event_type, payload)
        metadata_json = json.dumps(metadata, ensure_ascii=False)
        if existing is None:
            conn.execute(
                """
                INSERT INTO run_todos (
                    run_id, thread_id, todo_key, title, category, status,
                    progress_current, progress_total, task_id, agent_name,
                    last_event_type, started_at, completed_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    thread_id,
                    todo_key,
                    title,
                    category,
                    status or "pending",
                    0,
                    1,
                    task_id,
                    agent_name,
                    event_type,
                    now,
                    now if status in self.TERMINAL_STATUSES else None,
                    metadata_json,
                ),
            )
            return
        current_status = str(existing[0])
        if status is None:
            status = current_status
        completed_at = now if status in self.TERMINAL_STATUSES else None
        conn.execute(
            """
            UPDATE run_todos
            SET title = ?, category = ?, status = ?, task_id = COALESCE(?, task_id),
                agent_name = COALESCE(?, agent_name), last_event_type = ?, completed_at = ?,
                metadata_json = ?
            WHERE run_id = ? AND todo_key = ?
            """,
            (title, category, status, task_id, agent_name, event_type, completed_at, metadata_json, run_id, todo_key),
        )

    def _update_reasoning_progress(self, conn: sqlite3.Connection, *, run_id: str, todo_key: str, step_index: int, completed: bool) -> None:
        row = conn.execute(
            "SELECT progress_current, progress_total FROM run_todos WHERE run_id = ? AND todo_key = ?",
            (run_id, todo_key),
        ).fetchone()
        if row is None:
            return
        progress_current = max(int(row[0]), step_index + 1 if completed else int(row[0]))
        progress_total = max(int(row[1]), step_index + 1)
        conn.execute(
            "UPDATE run_todos SET progress_current = ?, progress_total = ? WHERE run_id = ? AND todo_key = ?",
            (progress_current, progress_total, run_id, todo_key),
        )

    def _finalize_open_items(self, conn: sqlite3.Connection, *, run_id: str, root_status: str) -> None:
        if root_status == "waiting_human":
            return
        target_status = "cancelled" if root_status == "completed" else "failed"
        conn.execute(
            """
            UPDATE run_todos
            SET status = ?, completed_at = COALESCE(completed_at, ?)
            WHERE run_id = ? AND todo_key != 'run:root' AND status = 'in_progress'
            """,
            (target_status, self._utc_now(), run_id),
        )

    def _fail_open_items(self, conn: sqlite3.Connection, *, run_id: str) -> None:
        conn.execute(
            """
            UPDATE run_todos
            SET status = 'failed', completed_at = COALESCE(completed_at, ?)
            WHERE run_id = ? AND status NOT IN ('completed', 'failed', 'cancelled', 'waiting_human')
            """,
            (self._utc_now(), run_id),
        )


class SQLiteEventStore(EventSink):
    def __init__(
        self,
        path: str | Path,
        *,
        capture_todos: bool = True,
        redaction: RedactionConfig | dict[str, object] | None = None,
        payload_budget: PayloadBudgetConfig | dict[str, object] | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.capture_todos = capture_todos
        self.redaction = RedactionConfig.from_any(redaction)
        self.payload_budget = PayloadBudgetConfig.from_any(payload_budget)
        self._initialize()
        self._todo_projection = TodoProjection(self._connect) if capture_todos else None

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    request_id TEXT,
                    run_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    trace_id TEXT,
                    task_id TEXT,
                    parent_task_id TEXT,
                    agent_name TEXT,
                    stage TEXT,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_run_events_run_id ON run_events(run_id, id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_run_events_thread_id ON run_events(thread_id, id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_run_events_event_type ON run_events(event_type)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    todo_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress_current INTEGER NOT NULL DEFAULT 0,
                    progress_total INTEGER NOT NULL DEFAULT 1,
                    task_id TEXT,
                    agent_name TEXT,
                    last_event_type TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uniq_run_todos ON run_todos(run_id, todo_key)")

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        event_record = shape_payload({"event_type": event_type, **payload}, budget=self.payload_budget, redaction=self.redaction)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO run_events (
                    created_at, event_type, request_id, run_id, thread_id, trace_id,
                    task_id, parent_task_id, agent_name, stage, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self._utc_now(),
                    event_type,
                    payload.get("request_id"),
                    str(payload.get("run_id") or ""),
                    str(payload.get("thread_id") or ""),
                    payload.get("trace_id"),
                    payload.get("task_id"),
                    payload.get("parent_task_id"),
                    payload.get("agent_name"),
                    payload.get("stage"),
                    json.dumps(event_record, ensure_ascii=False),
                ),
            )
        if self._todo_projection is not None:
            self._todo_projection.apply(event_type, payload)

    def get_run_events(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT payload_json FROM run_events WHERE run_id = ? ORDER BY id ASC", (run_id,)).fetchall()
        return [json.loads(str(row["payload_json"])) for row in rows]

    def get_thread_runs(self, thread_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    run_id,
                    thread_id,
                    MIN(created_at) AS started_at,
                    MAX(created_at) AS completed_at,
                    COUNT(*) AS event_count
                FROM run_events
                WHERE thread_id = ? AND run_id != ''
                GROUP BY run_id, thread_id
                ORDER BY MAX(id) DESC
                LIMIT ?
                """,
                (thread_id, limit),
            ).fetchall()
        summaries: list[dict[str, Any]] = []
        for row in rows:
            status = "in_progress"
            events = self.get_run_events(str(row["run_id"]))
            for event in reversed(events):
                event_type = event.get("event_type")
                if event_type == "run_failed":
                    status = "failed"
                    break
                if event_type == "run_completed":
                    status = str(event.get("status", "completed"))
                    break
            summaries.append(
                {
                    "run_id": row["run_id"],
                    "thread_id": row["thread_id"],
                    "started_at": row["started_at"],
                    "completed_at": row["completed_at"],
                    "status": status,
                    "event_count": int(row["event_count"]),
                }
            )
        return summaries

    def get_run_todos(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    run_id, thread_id, todo_key, title, category, status,
                    progress_current, progress_total, task_id, agent_name,
                    last_event_type, started_at, completed_at, metadata_json
                FROM run_todos
                WHERE run_id = ?
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()
        if not rows:
            return None
        items = []
        summary = {"total": 0, "completed": 0, "failed": 0, "waiting": 0, "in_progress": 0}
        root_status = "in_progress"
        thread_id = str(rows[0]["thread_id"])
        for row in rows:
            status = str(row["status"])
            summary["total"] += 1
            if status == "completed":
                summary["completed"] += 1
            elif status == "failed":
                summary["failed"] += 1
            elif status == "waiting_human":
                summary["waiting"] += 1
            elif status == "in_progress":
                summary["in_progress"] += 1
            if row["todo_key"] == "run:root":
                root_status = status
            items.append(
                {
                    "todo_key": row["todo_key"],
                    "title": row["title"],
                    "category": row["category"],
                    "status": status,
                    "progress_current": int(row["progress_current"]),
                    "progress_total": int(row["progress_total"]),
                    "task_id": row["task_id"],
                    "agent_name": row["agent_name"],
                    "last_event_type": row["last_event_type"],
                    "metadata": json.loads(str(row["metadata_json"])),
                }
            )
        return {"run_id": run_id, "thread_id": thread_id, "status": root_status, "summary": summary, "items": items}

    def get_latest_thread_todos(self, thread_id: str) -> dict[str, Any] | None:
        runs = self.get_thread_runs(thread_id, limit=1)
        if not runs:
            return None
        return self.get_run_todos(str(runs[0]["run_id"]))

    async def aclose(self) -> None:
        return None

    def close(self) -> None:
        return None


class ObservabilityManager(EventSink):
    def __init__(self, store: SQLiteEventStore | None = None) -> None:
        self.store = store
        self.enabled = store is not None

    @classmethod
    def disabled(cls) -> "ObservabilityManager":
        return cls(store=None)

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.store is not None:
            self.store.emit(event_type, payload)

    def get_run_events(self, run_id: str) -> list[dict[str, Any]]:
        if self.store is None:
            return []
        return self.store.get_run_events(run_id)

    def get_thread_runs(self, thread_id: str, limit: int = 20) -> list[dict[str, Any]]:
        if self.store is None:
            return []
        return self.store.get_thread_runs(thread_id, limit=limit)

    def get_run_todos(self, run_id: str) -> dict[str, Any] | None:
        if self.store is None:
            return None
        return self.store.get_run_todos(run_id)

    def get_latest_thread_todos(self, thread_id: str) -> dict[str, Any] | None:
        if self.store is None:
            return None
        return self.store.get_latest_thread_todos(thread_id)

    async def aclose(self) -> None:
        if self.store is None:
            return
        close_async = getattr(self.store, "aclose", None)
        if callable(close_async):
            await close_async()

    def close(self) -> None:
        if self.store is None:
            return
        close_sync = getattr(self.store, "close", None)
        if callable(close_sync):
            close_sync()


class Tracer:
    def __init__(self, event_bus: EventBus, logger: Logger | None = None, sinks: list[EventSink] | None = None) -> None:
        self.event_bus = event_bus
        self.logger = logger
        self.sinks = list(sinks or [])

    def add_sink(self, sink: EventSink) -> None:
        self.sinks.append(sink)

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        self.event_bus.publish(event_type, payload)
        for sink in self.sinks:
            sink.emit(event_type, payload)
        if self.logger:
            self.logger.log(event_type, payload)

    async def aclose(self) -> None:
        for sink in self.sinks:
            close_async = getattr(sink, "aclose", None)
            if callable(close_async):
                await close_async()


class ExecutionTrace:
    def __init__(self, events: list[dict[str, Any]] | None = None) -> None:
        self.events = events or []

    def event_types(self) -> list[str]:
        return [event.get("event_type", "") for event in self.events]


class TaskGraphSnapshot:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self.events = events

    def edges(self) -> list[tuple[str, str]]:
        graph_edges: list[tuple[str, str]] = []
        for event in self.events:
            task_id = event.get("task_id")
            parent_task_id = event.get("parent_task_id")
            if task_id and parent_task_id:
                graph_edges.append((parent_task_id, task_id))
        return graph_edges


class UsageTracker:
    def __init__(self) -> None:
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

    def add(self, usage: UsageInfo) -> None:
        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens
        self.total_tokens += usage.total_tokens

    def summary(self) -> UsageInfo:
        return UsageInfo(
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            total_tokens=self.total_tokens,
        )
