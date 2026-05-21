from __future__ import annotations

import random
from collections import defaultdict
from statistics import mean, pstdev
from typing import Any

from .schemas import ExperimentRecord, QUESTION_TYPES


def attach_relative_tokens(records: list[ExperimentRecord], *, reference_method: str = "no_long_term_memory") -> None:
    """给每条记录补相对 token 消耗。"""

    by_method: dict[str, list[int]] = defaultdict(list)
    for record in records:
        by_method[record.method].append(record.input_tokens)
    if reference_method in by_method and by_method[reference_method]:
        reference = mean(by_method[reference_method])
    elif records:
        reference = mean(record.input_tokens for record in records)
    else:
        reference = 1.0
    reference = max(1.0, float(reference))
    for record in records:
        record.relative_tokens = round(float(record.input_tokens) / reference, 4)


def aggregate_records(
    records: list[ExperimentRecord],
    *,
    bootstrap_samples: int = 300,
    full_variant_reference: str = "full",
) -> list[dict[str, Any]]:
    """按方法、variant、问题类型聚合实验指标。"""

    groups: dict[tuple[str, str, str], list[ExperimentRecord]] = defaultdict(list)
    for record in records:
        groups[(record.method, record.variant, record.question_type)].append(record)
        groups[(record.method, record.variant, "Overall")].append(record)

    rows: list[dict[str, Any]] = []
    ordered_question_types = [*QUESTION_TYPES, "Overall"]
    full_overall_accuracy: dict[str, float] = {}
    for (method, variant, question_type), items in groups.items():
        if variant == full_variant_reference and question_type == "Overall":
            full_overall_accuracy[method] = mean(float(item.judge_score) for item in items) * 100.0

    for (method, variant, question_type), items in sorted(
        groups.items(),
        key=lambda item: (
            item[0][0],
            item[0][1],
            ordered_question_types.index(item[0][2]) if item[0][2] in ordered_question_types else 99,
        ),
    ):
        scores = [float(item.judge_score) for item in items]
        input_tokens = [int(item.input_tokens) for item in items]
        latencies = [float(item.latency_ms) for item in items]
        detail_latencies = [float(item.detail_lookup_latency_ms) for item in items]
        relative_tokens = [item.relative_tokens for item in items]
        accuracy_mean = mean(scores) * 100.0
        accuracy_ci = _bootstrap_ci(scores, samples=bootstrap_samples, multiplier=100.0)
        row = {
            "method": method,
            "variant": variant,
            "question_type": question_type,
            "count": len(items),
            "accuracy_pct": round(accuracy_mean, 4),
            "accuracy_std": round(pstdev(scores) * 100.0, 4) if len(scores) > 1 else 0.0,
            "accuracy_ci_low": round(accuracy_ci[0], 4),
            "accuracy_ci_high": round(accuracy_ci[1], 4),
            "avg_input_tokens": round(mean(input_tokens), 4),
            "avg_relative_tokens": round(mean(relative_tokens), 4),
            "token_efficiency_score": round(accuracy_mean / max(0.0001, mean(relative_tokens)), 4),
            "avg_latency_ms": round(mean(latencies), 4),
            "avg_detail_lookup_latency_ms": round(mean(detail_latencies), 4),
            "detail_lookup_p50_ms": round(_percentile(detail_latencies, 50), 4),
            "detail_lookup_p95_ms": round(_percentile(detail_latencies, 95), 4),
            "capsule_hit_rate": round(mean(1.0 if item.target_capsule_hit else 0.0 for item in items), 4),
            "capsule_recall_at_k": round(mean(item.capsule_recall_at_k for item in items), 4),
            "relation_hit_rate": round(mean(1.0 if item.target_relation_hit else 0.0 for item in items), 4),
            "stale_injection_rate": round(mean(item.stale_node_injection_rate for item in items), 4),
            "conflict_success_rate": round(mean(item.conflict_resolution_success for item in items), 4),
            "evidence_completeness": round(mean(item.evidence_completeness for item in items), 4),
            "returned_memory_usefulness": round(mean(item.returned_memory_usefulness for item in items), 4),
            "revision_hit_rate": round(mean(item.revision_hit_rate for item in items), 4),
            "avg_returned_evidence_count": round(mean(item.returned_evidence_count for item in items), 4),
            "avg_returned_node_count": round(mean(item.returned_node_count for item in items), 4),
            "avg_returned_edge_count": round(mean(item.returned_edge_count for item in items), 4),
        }
        if question_type == "Overall" and variant != full_variant_reference and method in full_overall_accuracy:
            row["delta_vs_full"] = round(accuracy_mean - full_overall_accuracy[method], 4)
        else:
            row["delta_vs_full"] = 0.0
        rows.append(row)
    return rows


def _bootstrap_ci(values: list[float], *, samples: int, multiplier: float = 1.0) -> tuple[float, float]:
    """固定随机种子的 bootstrap 置信区间。"""

    if not values:
        return (0.0, 0.0)
    if len(values) == 1:
        value = values[0] * multiplier
        return (value, value)
    rng = random.Random(0)
    boot = []
    for _ in range(max(32, samples)):
        sample = [values[rng.randrange(len(values))] for _ in range(len(values))]
        boot.append(mean(sample) * multiplier)
    boot.sort()
    low_index = int(0.025 * (len(boot) - 1))
    high_index = int(0.975 * (len(boot) - 1))
    return boot[low_index], boot[high_index]


def _percentile(values: list[float], pct: int) -> float:
    """百分位工具函数。"""

    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = int(round((pct / 100.0) * (len(ordered) - 1)))
    return ordered[max(0, min(index, len(ordered) - 1))]
