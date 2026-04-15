from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from agentorch.security import RedactionConfig, sanitize_for_export


class SQLiteCheckpointStore:
    def __init__(self, path: str | Path, *, redaction: RedactionConfig | dict[str, object] | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.redaction = RedactionConfig.from_any(redaction)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    thread_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (thread_id, checkpoint_id)
                )
                """
            )

    async def save(self, thread_id: str, checkpoint_id: str, payload: dict[str, Any]) -> None:
        safe_payload = sanitize_for_export(payload, config=self.redaction)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO checkpoints(thread_id, checkpoint_id, payload) VALUES (?, ?, ?)",
                (thread_id, checkpoint_id, json.dumps(safe_payload, ensure_ascii=False)),
            )

    async def load(self, thread_id: str, checkpoint_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM checkpoints WHERE thread_id = ? AND checkpoint_id = ?",
                (thread_id, checkpoint_id),
            ).fetchone()
        return json.loads(row[0]) if row else None
