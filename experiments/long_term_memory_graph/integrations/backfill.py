from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..api.models import BackfillReport, ClaimSlot, MemoryCapsuleCandidate
from ..domain.utils import (
    derive_task_family,
    derive_thread_family,
    infer_agent_id,
    normalize_refs,
    normalize_string_list,
    normalize_text,
    stable_hash,
    synthetic_timestamp,
)


SUPPORTED_KINDS = {"episodic_capsule", "semantic_memory", "lesson_learned"}


def _safe_json_loads(value: str | None) -> dict[str, Any]:
    """安全解析旧库 metadata，格式异常时回空对象。"""

    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _parse_claims(value: Any) -> list[ClaimSlot]:
    """把旧库中的结构化 claims 转成 ClaimSlot。"""

    if not isinstance(value, list):
        return []
    claims: list[ClaimSlot] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        if "slot" not in item or "value" not in item:
            continue
        claims.append(ClaimSlot.model_validate(item))
    return claims


def _normalize_scope(metadata: dict[str, Any]) -> list[str]:
    """从旧 metadata 推导知识范围。"""

    scope_value = metadata.get("knowledge_scope")
    if scope_value:
        return normalize_string_list(scope_value)
    if metadata.get("scope"):
        return normalize_string_list(str(metadata["scope"]).split(","))
    return []


def _normalize_entities(metadata: dict[str, Any], thread_id: str) -> list[str]:
    """从 agent/thread 信息推导实体列表。"""

    values: list[str] = []
    if metadata.get("agent_role"):
        values.append(str(metadata["agent_role"]))
    for item in metadata.get("source_agents", []) or []:
        values.append(str(item))
    agent_id = infer_agent_id(thread_id, None)
    if agent_id:
        values.append(agent_id)
    return normalize_string_list(values)


def _candidate_from_row(
    *,
    source_path: Path,
    row_id: int,
    thread_id: str,
    kind: str,
    content: str,
    tags: list[str],
    metadata: dict[str, Any],
    ordinal: int,
) -> tuple[MemoryCapsuleCandidate, bool]:
    """把旧 records 表的一行转换成长期记忆胶囊。"""

    base_time = datetime.fromtimestamp(source_path.stat().st_mtime, tz=timezone.utc)
    created_at = metadata.get("created_at") or metadata.get("last_validated_at") or synthetic_timestamp(base_time, ordinal)
    goal = metadata.get("goal") or content
    task_id = metadata.get("task_id")
    candidate = MemoryCapsuleCandidate(
        capsule_id=f"legacy-{stable_hash({'path': str(source_path.resolve()), 'row_id': row_id, 'kind': kind}, length=20)}",
        agent_id=metadata.get("agent_role"),
        run_id=metadata.get("run_id"),
        thread_id=thread_id,
        thread_family=metadata.get("thread_family") or derive_thread_family(thread_id),
        task_id=task_id,
        task_family=metadata.get("task_family") or derive_task_family(task_id),
        created_at=created_at,
        goal=goal,
        summary=content,
        outcome=metadata.get("outcome") or content,
        knowledge_scope=_normalize_scope(metadata),
        tags=normalize_string_list([kind, "legacy_sqlite_backfill", *tags, *(metadata.get("tags") or [])]),
        entities=_normalize_entities(metadata, thread_id),
        claims=_parse_claims(metadata.get("claims")),
        evidence_refs=normalize_refs(metadata.get("evidence_refs")),
        source_memory_refs=normalize_refs(metadata.get("source_memory_refs")),
        salience_score=float(metadata.get("salience_score", 0.0) or 0.0),
        confidence=float(metadata.get("confidence", 0.5) or 0.5),
        status=normalize_text(metadata.get("status") or "validated"),
    )
    used_synthetic_time = "created_at" not in metadata and "last_validated_at" not in metadata
    return candidate, used_synthetic_time


def load_sqlite_backfill_candidates(records_db_path: str) -> tuple[list[MemoryCapsuleCandidate], BackfillReport]:
    """读取旧 SQLite records.db，生成可入图的候选胶囊。"""

    path = Path(records_db_path)
    if not path.exists():
        raise FileNotFoundError(f"SQLite records database does not exist: {path}")
    report = BackfillReport(source_path=str(path))
    candidates: list[MemoryCapsuleCandidate] = []
    synthetic_timestamp_count = 0
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            """
            SELECT id, thread_id, kind, content, tags, metadata
            FROM records
            WHERE kind IN (?, ?, ?)
            ORDER BY id ASC
            """,
            tuple(SUPPORTED_KINDS),
        ).fetchall()
    report.total_records = len(rows)
    for ordinal, row in enumerate(rows):
        row_id, thread_id, kind, content, tags_text, metadata_text = row
        if kind not in SUPPORTED_KINDS:
            report.skipped_records += 1
            continue
        content = normalize_text(content)
        if not content:
            report.skipped_records += 1
            continue
        try:
            row_tags = json.loads(tags_text or "[]")
        except json.JSONDecodeError:
            row_tags = []
        metadata = _safe_json_loads(metadata_text)
        candidate, used_synthetic_time = _candidate_from_row(
            source_path=path,
            row_id=int(row_id),
            thread_id=str(thread_id),
            kind=str(kind),
            content=content,
            tags=list(row_tags or []),
            metadata=metadata,
            ordinal=ordinal,
        )
        synthetic_timestamp_count += int(used_synthetic_time)
        candidates.append(candidate)
        report.imported_by_kind[kind] = report.imported_by_kind.get(kind, 0) + 1
    report.imported_capsules = len(candidates)
    report.skipped_records = max(report.skipped_records, report.total_records - report.imported_capsules)
    if synthetic_timestamp_count:
        report.notes.append(
            f"{synthetic_timestamp_count} records had no explicit timestamp; synthetic monotonic timestamps were assigned from file mtime."
        )
    report.notes.append(
        "Backfill only imports deterministic fields. REVISES and CONFLICTS_WITH require structured claims and will not be invented."
    )
    return candidates, report


class SQLiteBackfillImporter:
    """SQLite 回填执行器，只负责读取候选并调用写入函数。"""

    def __init__(self, store_capsules) -> None:
        self.store_capsules = store_capsules

    def import_from_sqlite(self, records_db_path: str) -> BackfillReport:
        """执行回填并返回报告。"""

        candidates, report = load_sqlite_backfill_candidates(records_db_path)
        if candidates:
            self.store_capsules(candidates)
        return report
