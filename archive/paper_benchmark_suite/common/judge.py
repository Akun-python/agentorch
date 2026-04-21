from __future__ import annotations

import json

from .config import TaskSpec


def score_output(*, task: TaskSpec, output_text: str) -> tuple[float, str]:
    text = (output_text or "").lower()
    rubric = task.rubric or {}
    required_terms = [str(item).lower() for item in rubric.get("required_terms", [])]
    if not required_terms:
        return (1.0 if output_text.strip() else 0.0, "non-empty output")
    matched = sum(1 for item in required_terms if item in text)
    return round(matched / max(1, len(required_terms)), 4), json.dumps({"matched_terms": matched, "required_terms": len(required_terms)}, ensure_ascii=False)
