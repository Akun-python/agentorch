from __future__ import annotations

from typing import Any


def compute_context_metrics(record_metadata: dict[str, Any], gold_segments: set[str]) -> dict[str, float]:
    selected = {item["segment_id"] for item in record_metadata.get("selected_context_segments", [])}
    if not selected and not gold_segments:
        return {
            "context_precision": 1.0,
            "context_recall": 1.0,
            "key_evidence_retention_rate": 1.0,
            "prompt_redundancy_ratio": 0.0,
        }
    true_positive = len(selected.intersection(gold_segments))
    precision = true_positive / max(1, len(selected))
    recall = true_positive / max(1, len(gold_segments))
    redundancy_ratio = len(record_metadata.get("dropped_context_segments", [])) / max(
        1,
        len(record_metadata.get("selected_context_segments", [])) + len(record_metadata.get("dropped_context_segments", [])),
    )
    return {
        "context_precision": round(precision, 4),
        "context_recall": round(recall, 4),
        "key_evidence_retention_rate": round(recall, 4),
        "prompt_redundancy_ratio": round(redundancy_ratio, 4),
    }
