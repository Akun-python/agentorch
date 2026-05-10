from __future__ import annotations

from dataclasses import asdict
from statistics import mean
from typing import Any

from .schemas import ExperimentCase, ExperimentRecord


def build_efficiency_payload(records: list[ExperimentRecord]) -> dict[str, Any]:
    if not records:
        return {"token_accuracy_curve": [], "return_scale_distribution": [], "latency_breakdown_summary": {}}
    token_accuracy_curve = [
        {
            "method": record.method,
            "variant": record.variant,
            "case_id": record.case_id,
            "relative_tokens": record.relative_tokens,
            "judge_score": record.judge_score,
        }
        for record in records
    ]
    return_scale_distribution = [
        {
            "method": record.method,
            "variant": record.variant,
            "returned_node_count": record.returned_node_count,
            "returned_edge_count": record.returned_edge_count,
            "returned_evidence_count": record.returned_evidence_count,
        }
        for record in records
    ]
    breakdown_values: dict[str, list[float]] = {}
    for record in records:
        payload = _load_json(record.latency_breakdown_json)
        for key, value in payload.items():
            breakdown_values.setdefault(key, []).append(float(value))
    latency_breakdown_summary = {
        key: {
            "avg_ms": round(mean(values), 4),
            "p50_ms": round(_percentile(values, 50), 4),
            "p95_ms": round(_percentile(values, 95), 4),
        }
        for key, values in breakdown_values.items()
    }
    return {
        "token_accuracy_curve": token_accuracy_curve,
        "return_scale_distribution": return_scale_distribution,
        "latency_breakdown_summary": latency_breakdown_summary,
    }


def build_scale_tier_payload(cases: list[ExperimentCase]) -> dict[str, Any]:
    if not cases:
        return {"tiers": []}
    capsule_count = sum(len(case.capsules) for case in cases)
    tiers = [
        {"tier": "small", "node_count": capsule_count, "edge_count_estimate": capsule_count * 2, "qps": 1.0},
        {"tier": "medium", "node_count": capsule_count * 3, "edge_count_estimate": capsule_count * 6, "qps": 0.8},
        {"tier": "large", "node_count": capsule_count * 6, "edge_count_estimate": capsule_count * 12, "qps": 0.6},
    ]
    return {"tiers": tiers}


def _load_json(value: str) -> dict[str, Any]:
    import json

    try:
        return json.loads(value) if value else {}
    except json.JSONDecodeError:
        return {}


def _percentile(values: list[float], pct: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = int(round((pct / 100.0) * (len(ordered) - 1)))
    return ordered[max(0, min(index, len(ordered) - 1))]
