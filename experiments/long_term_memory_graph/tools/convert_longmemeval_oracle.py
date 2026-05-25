from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from tqdm.auto import tqdm

from ..core.llm_extraction import LLMStructuredMemoryExtractor, StructuredMemoryExtraction


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
    parser.add_argument("--llm-extract", action="store_true", help="用 OpenAI-compatible flash 模型补全 summary/entities/claims。")
    parser.add_argument("--model-backend", default="openai_http", choices=["openai", "openai_http"], help="LLM 抽取使用的模型后端。")
    parser.add_argument("--model", default=None, help="LLM 抽取使用的模型名；也可由 .env 或环境变量提供。")
    parser.add_argument("--env-file", default=".env", help="LLM 抽取加载的 env 文件路径。")
    parser.add_argument("--no-env-file", action="store_true", help="禁用 env 文件，仅使用当前进程环境变量。")
    parser.add_argument("--overwrite-env", action="store_true", help="允许 env 文件覆盖当前进程已有环境变量。")
    parser.add_argument("--extract-log", default=None, help="可选 JSONL 日志，记录 LLM 抽取 token、耗时和失败原因。")
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
    extractor: LLMStructuredMemoryExtractor | None = None,
    extract_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """把 LongMemEval 的一个 haystack session 转成记忆胶囊。"""

    lines = list(_iter_turn_lines(session))
    session_text = "\n".join(lines)
    answer_lines = [_normalize_text(turn.get("content", "")) for turn in session if bool(turn.get("has_answer"))]
    answer_lines = [line for line in answer_lines if line]
    user_lines = [_normalize_text(turn.get("content", "")) for turn in session if _normalize_text(turn.get("role", "")) == "user"]
    goal = user_lines[0] if user_lines else (lines[0] if lines else session_id)
    summary = answer_lines[0] if answer_lines else (lines[0] if lines else session_id)
    created_at = _parse_longmemeval_dt(session_date, fallback_index=position).isoformat()
    extraction = _extract_session_structure(
        extractor,
        session_text=session_text,
        session_id=session_id,
        question_type=question_type,
        created_at=created_at,
        extract_events=extract_events,
    )
    if extraction is not None and extraction.summary:
        summary = extraction.summary
    return {
        "capsule_id": session_id,
        "thread_id": session_id,
        "task_id": question_id,
        "created_at": created_at,
        "goal": goal[:400],
        "summary": summary[:800],
        "outcome": session_text[:4000],
        "knowledge_scope": _slug_tokens(question_type.replace("-", " "))[:4],
        "tags": [question_type, "longmemeval", "oracle"],
        "entities": extraction.entities if extraction is not None else [],
        "claims": extraction.claims if extraction is not None else [],
        "evidence_refs": [session_id],
        "source_memory_refs": [],
        "salience_score": 0.8,
        "confidence": extraction.confidence if extraction is not None else (0.9 if answer_lines else 0.7),
        "status": "validated" if answer_lines else "candidate",
    }


def _map_question_type(raw_type: str, question_id: str) -> str | None:
    """把 LongMemEval 问题类型映射到本实验四类问题。"""

    if question_id.endswith("_abs"):
        return "Open Domain"
    return QUESTION_TYPE_MAP.get(raw_type)


def _extract_session_structure(
    extractor: LLMStructuredMemoryExtractor | None,
    *,
    session_text: str,
    session_id: str,
    question_type: str,
    created_at: str,
    extract_events: list[dict[str, Any]] | None,
) -> StructuredMemoryExtraction | None:
    """可选调用 LLM 抽取器；失败时保留原转换字段。"""

    if extractor is None or not session_text.strip():
        return None
    try:
        extraction = extractor.extract(
            session_text=session_text,
            session_id=session_id,
            question_type=question_type,
            created_at=created_at,
        )
    except Exception as exc:  # pragma: no cover - 真实 API 网络错误只记录不阻断转换
        if extract_events is not None:
            extract_events.append(
                {
                    "session_id": session_id,
                    "status": "error",
                    "error": str(exc),
                    "model_backend": extractor.model_backend,
                    "model": extractor.model_name,
                }
            )
        return None
    if extract_events is not None:
        extract_events.append(
            {
                "session_id": session_id,
                "status": "ok" if not extraction.parse_error else "parse_error",
                "parse_error": extraction.parse_error,
                "model_backend": extractor.model_backend,
                "model": extractor.model_name,
                "prompt_tokens": extraction.metrics.prompt_tokens,
                "completion_tokens": extraction.metrics.completion_tokens,
                "total_tokens": extraction.metrics.total_tokens,
                "duration_ms": round(extraction.metrics.duration_ms, 4),
                "claim_count": len(extraction.claims),
                "entity_count": len(extraction.entities),
            }
        )
    if extraction.parse_error:
        return None
    return extraction


def _build_case(
    item: dict[str, Any],
    *,
    include_abstention: bool,
    extractor: LLMStructuredMemoryExtractor | None = None,
    extract_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
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
            extractor=extractor,
            extract_events=extract_events,
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

    case_entities = sorted({entity for capsule in capsules for entity in capsule.get("entities", [])})
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
        "entities": case_entities,
        "case_tags": ["longmemeval", "oracle", raw_question_type],
        "token_budget": 4096 if mapped_type in {"Temporal", "Multi-hop"} else 2048,
        "notes": f"question_date={question_date}; llm_extract={bool(extractor)}",
    }


def _estimate_total_cases(data: list[dict[str, Any]], *, include_abstention: bool, limit: int | None) -> int:
    """预估将要写出的 case 数，用于 tqdm 总量。"""

    total = 0
    for item in data:
        question_id = _normalize_text(item.get("question_id"))
        raw_question_type = _normalize_text(item.get("question_type"))
        mapped_type = _map_question_type(raw_question_type, question_id)
        if mapped_type is None:
            continue
        if question_id.endswith("_abs") and not include_abstention:
            continue
        answer_session_ids = [str(value) for value in item.get("answer_session_ids", [])]
        if not answer_session_ids and not include_abstention:
            continue
        total += 1
        if limit is not None and total >= limit:
            break
    return total


def main() -> int:
    """执行转换并输出转换摘要。"""

    args = _parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    extractor = (
        LLMStructuredMemoryExtractor(
            model_backend=args.model_backend,
            model_name=args.model,
            env_file=args.env_file,
            load_env=not args.no_env_file,
            overwrite_env=args.overwrite_env,
        )
        if args.llm_extract
        else None
    )

    rows: list[dict[str, Any]] = []
    skipped_abstention = 0
    skipped_unsupported = 0
    extract_events: list[dict[str, Any]] = []
    total_cases = _estimate_total_cases(data, include_abstention=args.include_abstention, limit=args.limit)
    progress = tqdm(total=total_cases, desc="convert_longmemeval_oracle", unit="case", dynamic_ncols=True)
    try:
        for item in data:
            question_id = _normalize_text(item.get("question_id"))
            progress.set_postfix_str(question_id or "unknown")
            row = _build_case(
                item,
                include_abstention=args.include_abstention,
                extractor=extractor,
                extract_events=extract_events,
            )
            if row is None:
                raw_question_type = _normalize_text(item.get("question_type"))
                if question_id.endswith("_abs") and not args.include_abstention:
                    skipped_abstention += 1
                else:
                    skipped_unsupported += 1
                continue
            rows.append(row)
            progress.update(1)
            if args.limit is not None and len(rows) >= args.limit:
                break
    finally:
        progress.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    extract_log_path = Path(args.extract_log) if args.extract_log else None
    if extract_log_path is not None:
        extract_log_path.parent.mkdir(parents=True, exist_ok=True)
        with extract_log_path.open("w", encoding="utf-8", newline="\n") as handle:
            for event in extract_events:
                handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    summary = {
        "input": str(input_path.resolve()),
        "output": str(output_path.resolve()),
        "written_cases": len(rows),
        "skipped_abstention": skipped_abstention,
        "skipped_unsupported": skipped_unsupported,
        "include_abstention": bool(args.include_abstention),
        "llm_extract": bool(args.llm_extract),
        "extract_event_count": len(extract_events),
        "extract_log": str(extract_log_path.resolve()) if extract_log_path is not None else None,
        "limit": args.limit,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
