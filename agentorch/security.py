from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


_DEFAULT_SENSITIVE_KEYS = [
    "api_key",
    "authorization",
    "token",
    "secret",
    "password",
    "cookie",
    "set-cookie",
    "x-api-key",
]
_DEFAULT_PRESERVE_KEYS = [
    "event_type",
    "request_id",
    "run_id",
    "thread_id",
    "trace_id",
    "task_id",
    "parent_task_id",
    "agent_name",
    "stage",
    "status",
    "tool_name",
    "feedback_id",
    "kind",
    "severity",
    "blocking",
]
_SECRET_VALUE_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]+\b", re.IGNORECASE),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]


class RedactionConfig(BaseModel):
    enabled: bool = True
    mode: Literal["mask", "off"] = "mask"
    mask: str = "[REDACTED]"
    unsafe_export: bool = False
    sensitive_keys: list[str] = Field(default_factory=lambda: list(_DEFAULT_SENSITIVE_KEYS))
    sensitive_key_patterns: list[str] = Field(default_factory=list)
    sensitive_value_patterns: list[str] = Field(default_factory=list)

    @classmethod
    def from_any(cls, value: "RedactionConfig | dict[str, object] | None") -> "RedactionConfig":
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value.model_copy(deep=True)
        return cls.model_validate(value)


class PayloadBudgetConfig(BaseModel):
    max_total_chars: int = 12000
    max_string_chars: int = 1600
    max_collection_items: int = 20
    max_depth: int = 6
    preserve_keys: list[str] = Field(default_factory=lambda: list(_DEFAULT_PRESERVE_KEYS))

    @classmethod
    def from_any(cls, value: "PayloadBudgetConfig | dict[str, object] | None") -> "PayloadBudgetConfig":
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value.model_copy(deep=True)
        return cls.model_validate(value)


def summarize_text(text: str, *, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "...[truncated]"


def _normalize_key(key: Any) -> str:
    return str(key).strip().lower().replace("_", "-")


def _compiled_key_patterns(config: RedactionConfig) -> list[re.Pattern[str]]:
    return [re.compile(pattern, re.IGNORECASE) for pattern in config.sensitive_key_patterns]


def _compiled_value_patterns(config: RedactionConfig) -> list[re.Pattern[str]]:
    compiled = list(_SECRET_VALUE_PATTERNS)
    compiled.extend(re.compile(pattern, re.IGNORECASE) for pattern in config.sensitive_value_patterns)
    return compiled


def _looks_sensitive_key(path: tuple[str, ...], config: RedactionConfig) -> bool:
    normalized_path = [_normalize_key(part) for part in path if part]
    key_patterns = _compiled_key_patterns(config)
    for part in normalized_path:
        if any(token in part for token in config.sensitive_keys):
            return True
        if any(pattern.search(part) for pattern in key_patterns):
            return True
    return False


def _redact_text(value: str, *, config: RedactionConfig) -> str:
    if config.mode == "off":
        return value
    redacted = value
    for pattern in _compiled_value_patterns(config):
        redacted = pattern.sub(config.mask, redacted)
    return redacted


def sanitize_for_export(
    value: Any,
    *,
    config: RedactionConfig | dict[str, object] | None = None,
    unsafe: bool = False,
    path: tuple[str, ...] = (),
) -> Any:
    resolved = RedactionConfig.from_any(config)
    if unsafe or resolved.unsafe_export or not resolved.enabled or resolved.mode == "off":
        if isinstance(value, BaseModel):
            return {key: sanitize_for_export(item, config=resolved, unsafe=True, path=path + (str(key),)) for key, item in value.model_dump(exclude_none=True).items()}
        if isinstance(value, dict):
            return {str(key): sanitize_for_export(item, config=resolved, unsafe=True, path=path + (str(key),)) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [sanitize_for_export(item, config=resolved, unsafe=True, path=path) for item in value]
        if hasattr(value, "value") and not isinstance(value, str):
            return getattr(value, "value", repr(value))
        if isinstance(value, os.PathLike):
            return str(value)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return repr(value)

    if _looks_sensitive_key(path, resolved):
        return resolved.mask
    if isinstance(value, BaseModel):
        return {
            key: sanitize_for_export(item, config=resolved, path=path + (str(key),))
            for key, item in value.model_dump(exclude_none=True).items()
        }
    if isinstance(value, dict):
        return {
            str(key): sanitize_for_export(item, config=resolved, path=path + (str(key),))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_export(item, config=resolved, path=path) for item in value]
    if hasattr(value, "value") and not isinstance(value, str):
        return getattr(value, "value", repr(value))
    if isinstance(value, os.PathLike):
        return str(value)
    if isinstance(value, str):
        return _redact_text(value, config=resolved)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _redact_text(repr(value), config=resolved)


def _compact_value(value: Any, *, budget: PayloadBudgetConfig, depth: int = 0) -> Any:
    if depth >= budget.max_depth:
        return {"summary": summarize_text(json.dumps(sanitize_for_export(value), ensure_ascii=False), max_chars=budget.max_string_chars), "truncated": True}
    if isinstance(value, str):
        return summarize_text(value, max_chars=budget.max_string_chars)
    if isinstance(value, dict):
        items = list(value.items())
        compacted: dict[str, Any] = {}
        for index, (key, item) in enumerate(items):
            if index >= budget.max_collection_items:
                compacted["_truncated_keys"] = len(items) - budget.max_collection_items
                break
            compacted[str(key)] = _compact_value(item, budget=budget, depth=depth + 1)
        return compacted
    if isinstance(value, list):
        compacted_list = [_compact_value(item, budget=budget, depth=depth + 1) for item in value[: budget.max_collection_items]]
        if len(value) > budget.max_collection_items:
            compacted_list.append({"summary": f"{len(value) - budget.max_collection_items} more items", "truncated": True})
        return compacted_list
    if isinstance(value, tuple):
        return _compact_value(list(value), budget=budget, depth=depth)
    return value


def shape_payload(
    payload: dict[str, Any],
    *,
    budget: PayloadBudgetConfig | dict[str, object] | None = None,
    redaction: RedactionConfig | dict[str, object] | None = None,
) -> dict[str, Any]:
    resolved_budget = PayloadBudgetConfig.from_any(budget)
    sanitized = sanitize_for_export(payload, config=redaction)
    redaction_applied = sanitized != payload
    if not isinstance(sanitized, dict):
        return {
            "payload_summary": summarize_text(json.dumps(sanitized, ensure_ascii=False), max_chars=resolved_budget.max_total_chars),
            "full_payload_available": False,
            "redaction_applied": redaction_applied,
        }
    shaped = _compact_value(sanitized, budget=resolved_budget)
    serialized = json.dumps(shaped, ensure_ascii=False, sort_keys=True)
    if len(serialized) <= resolved_budget.max_total_chars:
        result = dict(shaped)
        result["redaction_applied"] = redaction_applied
        return result

    reduced = dict(shaped)
    candidate_keys = [key for key in reduced if key not in resolved_budget.preserve_keys]
    candidate_keys.sort(
        key=lambda key: len(json.dumps(reduced.get(key), ensure_ascii=False, sort_keys=True)),
        reverse=True,
    )
    for key in candidate_keys:
        value = reduced[key]
        reduced[key] = {
            "summary": summarize_text(json.dumps(value, ensure_ascii=False, sort_keys=True), max_chars=min(resolved_budget.max_string_chars, 400)),
            "full_payload_available": False,
        }
        serialized = json.dumps(reduced, ensure_ascii=False, sort_keys=True)
        if len(serialized) <= resolved_budget.max_total_chars:
            break
    if len(serialized) > resolved_budget.max_total_chars:
        return {
            key: reduced[key]
            for key in reduced
            if key in resolved_budget.preserve_keys and key in reduced
        } | {
            "payload_summary": summarize_text(serialized, max_chars=resolved_budget.max_total_chars),
            "full_payload_available": False,
            "redaction_applied": True,
        }
    reduced["redaction_applied"] = True
    return reduced


def summarize_tool_output(
    *,
    label: str,
    content: str,
    budget_chars: int,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    preview = summarize_text(content, max_chars=budget_chars)
    return {
        "summary": f"{label}: {len(content)} chars" + (" (truncated)" if len(preview) < len(content) else ""),
        "preview": preview,
        "truncated": len(preview) < len(content),
        **(metadata or {}),
    }
