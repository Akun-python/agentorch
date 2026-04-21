from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterable

from .config import RunRecord
from .io import load_existing_records
from .stats import approximate_p_value, ci95, cohen_d, safe_mean, safe_std


def aggregate_records(records: Iterable[RunRecord], *, group_by: list[str], metric_fields: list[str]) -> list[dict]:
    buckets: dict[tuple, list[RunRecord]] = defaultdict(list)
    for record in records:
        key = tuple(getattr(record, field) for field in group_by)
        buckets[key].append(record)

    rows: list[dict] = []
    for key, bucket in buckets.items():
        row = {field: value for field, value in zip(group_by, key)}
        row["n"] = len(bucket)
        for metric in metric_fields:
            values = [float(getattr(item, metric)) for item in bucket]
            low, high = ci95(values)
            row[f"{metric}_mean"] = round(safe_mean(values), 4)
            row[f"{metric}_std"] = round(safe_std(values), 4)
            row[f"{metric}_ci95_low"] = round(low, 4)
            row[f"{metric}_ci95_high"] = round(high, 4)
        rows.append(row)
    return rows


def compare_variants(records: Iterable[RunRecord], *, metric: str, reference_variant: str, compare_variant: str) -> dict:
    lhs = [float(getattr(item, metric)) for item in records if item.variant_name == reference_variant]
    rhs = [float(getattr(item, metric)) for item in records if item.variant_name == compare_variant]
    low_ref, high_ref = ci95(lhs)
    low_cmp, high_cmp = ci95(rhs)
    return {
        "reference_variant": reference_variant,
        "compare_variant": compare_variant,
        "metric": metric,
        "reference_mean": round(safe_mean(lhs), 4),
        "reference_ci95_low": round(low_ref, 4),
        "reference_ci95_high": round(high_ref, 4),
        "compare_mean": round(safe_mean(rhs), 4),
        "compare_ci95_low": round(low_cmp, 4),
        "compare_ci95_high": round(high_cmp, 4),
        "effect_size_cohen_d": round(cohen_d(lhs, rhs), 4),
        "approx_p_value": round(approximate_p_value(lhs, rhs), 6),
    }


def collect_records(result_root: Path) -> list[RunRecord]:
    records: list[RunRecord] = []
    for results_file in result_root.rglob("results.jsonl"):
        records.extend(load_existing_records(results_file.parent))
    return records
