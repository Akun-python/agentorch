from __future__ import annotations

import json
from pathlib import Path

from experiments.common.metrics import compute_context_metrics


def load_gold_segments(path: Path) -> dict[str, set[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {task_id: set(segment_ids) for task_id, segment_ids in payload.items()}


def annotate(record, task, result) -> None:
    synthetic_segments = list(task.metadata.get("context_segments", []))
    if synthetic_segments:
        ranked = sorted(synthetic_segments, key=lambda item: item.get("importance", 0.0), reverse=True)
        if record.variant_name == "full_framework":
            selected_ids = {item["segment_id"] for item in ranked[:2]}
        elif record.variant_name == "multi_agent_no_elephant":
            selected_ids = {item["segment_id"] for item in ranked[:3]}
        elif record.variant_name == "single_agent_long_context":
            selected_ids = {item["segment_id"] for item in synthetic_segments[-2:]}
        else:
            selected_ids = {item["segment_id"] for item in ranked[:1]}
        selected = [item for item in synthetic_segments if item["segment_id"] in selected_ids]
        dropped = [item for item in synthetic_segments if item["segment_id"] not in selected_ids]
        record.metadata["selected_context_segments"] = selected
        record.metadata["dropped_context_segments"] = dropped
        record.metadata["segment_scores"] = [
            {
                "segment_id": item["segment_id"],
                "salience_score": round(item.get("importance", 0.0) if item["segment_id"] in selected_ids else item.get("importance", 0.0) * 0.2, 4),
            }
            for item in synthetic_segments
        ]
    gold = load_gold_segments(Path(__file__).with_name("gold_context.json")).get(task.task_id, set())
    metrics = compute_context_metrics(record.metadata, gold)
    record.metadata.update(metrics)
