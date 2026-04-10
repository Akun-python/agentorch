from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class SQLiteRecordStore:
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
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(records)").fetchall()}
            if "metadata" not in columns:
                conn.execute("ALTER TABLE records ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'")

    async def add_record(self, thread_id: str, kind: str, content: str, tags: list[str], metadata: dict[str, Any] | None = None) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO records(thread_id, kind, content, tags, metadata) VALUES (?, ?, ?, ?, ?)",
                (thread_id, kind, content, json.dumps(tags, ensure_ascii=False), json.dumps(metadata or {}, ensure_ascii=False)),
            )
            return int(cursor.lastrowid)

    async def search(
        self,
        thread_id: str | None = None,
        query: str | None = None,
        tags: list[str] | None = None,
        metadata_filters: dict[str, Any] | None = None,
        kinds: list[str] | None = None,
        limit: int | None = None,
        order_desc: bool = False,
    ) -> list[dict[str, Any]]:
        sql = "SELECT id, thread_id, kind, content, tags, metadata FROM records WHERE 1=1"
        params: list[Any] = []
        if thread_id:
            sql += " AND thread_id = ?"
            params.append(thread_id)
        if query:
            sql += " AND content LIKE ?"
            params.append(f"%{query}%")
        if kinds:
            sql += " AND kind IN (" + ", ".join("?" for _ in kinds) + ")"
            params.extend(kinds)
        sql += " ORDER BY id DESC" if order_desc else " ORDER BY id ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        results = []
        for row in rows:
            row_tags = json.loads(row[4])
            if tags and not set(tags).issubset(set(row_tags)):
                continue
            row_metadata = json.loads(row[5] or "{}")
            if metadata_filters:
                if any(row_metadata.get(key) != value for key, value in metadata_filters.items()):
                    continue
            results.append(
                {
                    "id": row[0],
                    "thread_id": row[1],
                    "kind": row[2],
                    "content": row[3],
                    "tags": row_tags,
                    "metadata": row_metadata,
                }
            )
        return results

    async def update_record_metadata(self, record_id: int, metadata: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE records SET metadata = ? WHERE id = ?",
                (json.dumps(metadata, ensure_ascii=False), record_id),
            )
