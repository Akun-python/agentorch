from __future__ import annotations

import asyncio
import hashlib
import json
import re
import threading
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc_datetime(value: datetime | str | None, *, fallback: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    if fallback is not None:
        return ensure_utc_datetime(fallback)
    return now_utc()


def to_iso8601(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    return ensure_utc_datetime(value).isoformat()


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def normalize_token(value: Any) -> str:
    return normalize_text(value).lower()


def normalize_string_list(values: Iterable[Any] | None) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for item in values or []:
        token = normalize_token(item)
        if not token or token in seen:
            continue
        seen.add(token)
        normalized.append(token)
    return normalized


def normalize_refs(values: Iterable[Any] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in values or []:
        if isinstance(item, dict):
            parts = [f"{normalize_token(key)}={normalize_token(value)}" for key, value in sorted(item.items()) if normalize_token(value)]
            token = "|".join(parts)
        else:
            token = normalize_token(item)
        if not token or token in seen:
            continue
        seen.add(token)
        normalized.append(token)
    return normalized


def stable_hash(payload: Any, *, length: int = 16) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:length]


def jaccard_similarity(left: Iterable[Any] | None, right: Iterable[Any] | None) -> float:
    left_set = set(normalize_string_list(left))
    right_set = set(normalize_string_list(right))
    if not left_set and not right_set:
        return 0.0
    return len(left_set.intersection(right_set)) / float(len(left_set.union(right_set)))


def derive_thread_family(thread_id: str | None) -> str | None:
    token = normalize_text(thread_id)
    if not token:
        return None
    if ":" in token:
        return token.split(":", 1)[0]
    match = re.match(r"^(.*)-rep-\d+$", token)
    if match:
        return match.group(1)
    return token


def derive_task_family(task_id: str | None) -> str | None:
    token = normalize_text(task_id)
    if not token:
        return None
    if ":" in token:
        return token.split(":", 1)[0]
    return token


def infer_agent_id(thread_id: str | None, explicit: str | None = None) -> str | None:
    token = normalize_text(explicit)
    if token:
        return token
    raw_thread = normalize_text(thread_id)
    if ":" in raw_thread:
        return raw_thread.rsplit(":", 1)[-1]
    return None


def truncate_text(text: str | None, *, max_chars: int = 160) -> str:
    value = normalize_text(text)
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."


def synthetic_timestamp(base_time: datetime, ordinal: int) -> datetime:
    return ensure_utc_datetime(base_time) + timedelta(seconds=max(0, ordinal))


def run_async(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    outcome: dict[str, Any] = {}

    def _runner() -> None:
        try:
            outcome["value"] = asyncio.run(coro)
        except Exception as exc:  # pragma: no cover - propagated to caller
            outcome["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")
