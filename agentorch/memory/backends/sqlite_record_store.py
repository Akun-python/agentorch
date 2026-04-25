from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from agentorch.security import RedactionConfig, sanitize_for_export, summarize_text


class SQLiteRecordStore:
    def __init__(
        self,
        path: str | Path,
        *,
        redaction: RedactionConfig | dict[str, object] | None = None,
        summary_only_content: bool = False,
        max_content_chars: int = 8000,
        max_metadata_chars: int = 4000,
        truncate_thread_messages: bool = True,
        persist_full_prompt_text: bool = False,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.redaction = RedactionConfig.from_any(redaction)
        self.summary_only_content = summary_only_content
        self.max_content_chars = max(200, int(max_content_chars))
        self.max_metadata_chars = max(200, int(max_metadata_chars))
        self.truncate_thread_messages = truncate_thread_messages
        self.persist_full_prompt_text = persist_full_prompt_text
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

    def _prepare_content(self, kind: str, content: str) -> tuple[str, dict[str, Any]]:
        original_length = len(content)
        force_summary = self.summary_only_content
        if kind == "thread_message" and self.truncate_thread_messages:
            force_summary = force_summary or not self.persist_full_prompt_text
        if force_summary:
            stored = summarize_text(content, max_chars=min(self.max_content_chars, 800))
        else:
            stored = summarize_text(content, max_chars=self.max_content_chars)
        metadata: dict[str, Any] = {
            "original_length": original_length,
            "truncated": len(stored) < original_length,
        }
        return stored, metadata

    def _prepare_metadata(self, metadata: dict[str, Any] | None) -> dict[str, Any]:
        safe_metadata = sanitize_for_export(metadata or {}, config=self.redaction)
        serialized = json.dumps(safe_metadata, ensure_ascii=False, sort_keys=True)
        if len(serialized) <= self.max_metadata_chars:
            return safe_metadata
        return {
            "summary": summarize_text(serialized, max_chars=self.max_metadata_chars),
            "truncated": True,
            "original_length": len(serialized),
        }

    async def add_record(self, thread_id: str, kind: str, content: str, tags: list[str], metadata: dict[str, Any] | None = None) -> int:
        stored_content, content_metadata = self._prepare_content(kind, content)
        safe_metadata = self._prepare_metadata(metadata)
        safe_metadata = {**safe_metadata, "_storage": content_metadata}
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO records(thread_id, kind, content, tags, metadata) VALUES (?, ?, ?, ?, ?)",
                (thread_id, kind, stored_content, json.dumps(tags, ensure_ascii=False), json.dumps(safe_metadata, ensure_ascii=False)),
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
                (json.dumps(sanitize_for_export(metadata, config=self.redaction), ensure_ascii=False), record_id),
            )
