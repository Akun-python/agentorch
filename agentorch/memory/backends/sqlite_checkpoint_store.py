from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class SQLiteCheckpointStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
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
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO checkpoints(thread_id, checkpoint_id, payload) VALUES (?, ?, ?)",
                (thread_id, checkpoint_id, json.dumps(payload, ensure_ascii=False)),
            )

    async def load(self, thread_id: str, checkpoint_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM checkpoints WHERE thread_id = ? AND checkpoint_id = ?",
                (thread_id, checkpoint_id),
            ).fetchone()
        return json.loads(row[0]) if row else None
