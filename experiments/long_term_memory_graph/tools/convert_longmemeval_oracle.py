from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


QUESTION_TYPE_MAP = {
    "single-session-user": "Single-hop",
    "single-session-assistant": "Single-hop",
    "single-session-preference": "Single-hop",
    "temporal-reasoning": "Temporal",
    "knowledge-update": "Temporal",
    "multi-session": "Multi-hop",
}


def _parse_args() -> argparse.Namespace:
    """解析 LongMemEval oracle 转换参数。"""

    parser = argparse.ArgumentParser(description="将 LongMemEval oracle 数据转换为 long_term_memory_graph 可读 JSONL。")
    parser.add_argument("--input", required=True, help="LongMemEval oracle json 文件路径。")
    parser.add_argument("--output", required=True, help="输出 jsonl 路径。")
    parser.add_argument("--limit", type=int, default=None, help="仅转换前 N 条，便于烟测。")
    parser.add_argument("--include-abstention", action="store_true", help="默认跳过 abstention 样本；开启后保留。")
    return parser.parse_args()


def _parse_longmemeval_dt(raw: str, *, fallback_index: int = 0) -> datetime:
    """解析 LongMemEval 日期，并用秒偏移避免同会话时间完全相同。"""

    base = datetime.strptime(raw.strip(), "%Y/%m/%d (%a) %H:%M")
    return base.replace(tzinfo=timezone.utc) + timedelta(seconds=fallback_index)


def _normalize_text(value: Any) -> str:
    """清理空白文本。"""

    if value is None:
        return ""
    return " ".join(str(value).split())


def _slug_tokens(text: str) -> list[str]:
    """从问题类型中提取可放入 scope 的 token。"""

    tokens: list[str] = []
    current: list[str] = []
    for char in text.lower():
        if char.isalnum():
            current.append(char)
            continue
        if current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def _iter_turn_lines(session: list[dict[str, Any]]) -> Iterable[str]:
    """把一个会话展开成 role: content 行。"""

    for turn in session:
        role = _normalize_text(turn.get("role", "unknown")) or "unknown"
        content = _normalize_text(turn.get("content", ""))
        if not content:
            continue
        yield f"{role}: {content}"


def _build_capsule(
    *,
    question_id: str,
    question_type: str,
    session_id: str,
    session_date: str,
    session: list[dict[str, Any]],
    position: int,
) -> dict[str, Any]:
    """把 LongMemEval 的一个 haystack session 转成记忆胶囊。"""

    lines = list(_iter_turn_lines(session))
    session_text = "\n".join(lines)
    answer_lines = [_normalize_text(turn.get("content", "")) for turn in session if bool(turn.get("has_answer"))]
    answer_lines = [line for line in answer_lines if line]
    user_lines = [_normalize_text(turn.get("content", "")) for turn in session if _normalize_text(turn.get("role", "")) == "user"]
    goal = user_lines[0] if user_lines else (lines[0] if lines else session_id)
    summary = answer_lines[0] if answer_lines else (lines[0] if lines else session_id)
    return {
        "capsule_id": session_id,
        "thread_id": session_id,
        "task_id": question_id,
        "created_at": _parse_longmemeval_dt(session_date, fallback_index=position).isoformat(),
        "goal": goal[:400],
        "summary": summary[:800],
        "outcome": session_text[:4000],
        "knowledge_scope": _slug_tokens(question_type.replace("-", " "))[:4],
        "tags": [question_type, "longmemeval", "oracle"],
        "entities": [],
        "claims": [],
        "evidence_refs": [session_id],
        "source_memory_refs": [],
        "salience_score": 0.8,
        "confidence": 0.9 if answer_lines else 0.7,
        "status": "validated" if answer_lines else "candidate",
    }


def _map_question_type(raw_type: str, question_id: str) -> str | None:
    """把 LongMemEval 问题类型映射到本实验四类问题。"""

    if question_id.endswith("_abs"):
        return "Open Domain"
    return QUESTION_TYPE_MAP.get(raw_type)


def _build_case(item: dict[str, Any], *, include_abstention: bool) -> dict[str, Any] | None:
    """把 LongMemEval 单条样本转换成本实验 JSONL case。"""

    question_id = _normalize_text(item.get("question_id"))
    raw_question_type = _normalize_text(item.get("question_type"))
    mapped_type = _map_question_type(raw_question_type, question_id)
    if mapped_type is None:
        return None
    is_abstention = question_id.endswith("_abs")
    if is_abstention and not include_abstention:
        return None

    session_ids = list(item.get("haystack_session_ids", []))
    session_dates = list(item.get("haystack_dates", []))
    sessions = list(item.get("haystack_sessions", []))
    if not (len(session_ids) == len(session_dates) == len(sessions)):
        raise ValueError(f"LongMemEval item {question_id} has inconsistent haystack fields.")

    capsules = [
        _build_capsule(
            question_id=question_id,
            question_type=raw_question_type,
            session_id=str(session_id),
            session_date=str(session_date),
            session=session,
            position=index,
        )
        for index, (session_id, session_date, session) in enumerate(zip(session_ids, session_dates, sessions, strict=True))
    ]

    answer_session_ids = [str(value) for value in item.get("answer_session_ids", [])]
    if not answer_session_ids and not include_abstention:
        return None

    question = _normalize_text(item.get("question"))
    answer = _normalize_text(item.get("answer"))
    question_date = _normalize_text(item.get("question_date"))
    tags = [raw_question_type, "longmemeval", "oracle"]
    if is_abstention:
        tags.append("abstention")

    return {
        "case_id": f"longmemeval_oracle::{question_id}",
        "question_type": mapped_type,
        "query": question,
        "standard_answer": answer,
        "capsules": capsules,
        "target_capsule_ids": answer_session_ids,
        # LongMemEval oracle 只提供证据 session，不提供可直接对齐到图边标签的标准关系。
        "target_relation_types": [],
        "revision_target_ids": answer_session_ids if raw_question_type == "knowledge-update" else [],
        "stale_capsule_ids": [],
        "conflict_loser_ids": [],
        "detail_lookup_capsule_ids": answer_session_ids,
        "knowledge_scope": _slug_tokens(raw_question_type.replace("-", " "))[:4],
        "tags": tags,
        "entities": [],
        "case_tags": ["longmemeval", "oracle", raw_question_type],
        "token_budget": 4096 if mapped_type in {"Temporal", "Multi-hop"} else 2048,
        "notes": f"question_date={question_date}",
    }


def main() -> int:
    """执行转换并输出转换摘要。"""

    args = _parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    data = json.loads(input_path.read_text(encoding="utf-8"))

    rows: list[dict[str, Any]] = []
    skipped_abstention = 0
    skipped_unsupported = 0

    for item in data:
        row = _build_case(item, include_abstention=args.include_abstention)
        if row is None:
            question_id = _normalize_text(item.get("question_id"))
            raw_question_type = _normalize_text(item.get("question_type"))
            if question_id.endswith("_abs") and not args.include_abstention:
                skipped_abstention += 1
            else:
                skipped_unsupported += 1
            continue
        rows.append(row)
        if args.limit is not None and len(rows) >= args.limit:
            break

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "input": str(input_path.resolve()),
        "output": str(output_path.resolve()),
        "written_cases": len(rows),
        "skipped_abstention": skipped_abstention,
        "skipped_unsupported": skipped_unsupported,
        "include_abstention": bool(args.include_abstention),
        "limit": args.limit,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
