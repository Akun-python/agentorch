from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class InMemoryStateStore:
    def __init__(self) -> None:
        self._state: dict[str, dict[str, Any]] = {}

    async def get_state(self, thread_id: str) -> dict[str, Any]:
        return self._state.setdefault(thread_id, {})

    async def set_state(self, thread_id: str, state: dict[str, Any]) -> None:
        self._state[thread_id] = state


class SQLiteCheckpointStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

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


class SQLiteRecordStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL
                )
                """
            )

    async def add_record(self, thread_id: str, kind: str, content: str, tags: list[str]) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO records(thread_id, kind, content, tags) VALUES (?, ?, ?, ?)",
                (thread_id, kind, content, json.dumps(tags, ensure_ascii=False)),
            )
            return int(cursor.lastrowid)

    async def search(self, thread_id: str | None = None, query: str | None = None, tags: list[str] | None = None) -> list[dict[str, Any]]:
        sql = "SELECT id, thread_id, kind, content, tags FROM records WHERE 1=1"
        params: list[Any] = []
        if thread_id:
            sql += " AND thread_id = ?"
            params.append(thread_id)
        if query:
            sql += " AND content LIKE ?"
            params.append(f"%{query}%")
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        results = []
        for row in rows:
            row_tags = json.loads(row[4])
            if tags and not set(tags).issubset(set(row_tags)):
                continue
            results.append({"id": row[0], "thread_id": row[1], "kind": row[2], "content": row[3], "tags": row_tags})
        return results
