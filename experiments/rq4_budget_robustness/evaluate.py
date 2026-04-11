from __future__ import annotations


def _select_segments(record, task):
    budget = int(record.metadata.get("prompt_budget") or record.metadata.get("context_budget_report", {}).get("prompt_char_budget") or 0)
    segments = list(task.metadata.get("segments", []))
    if not segments:
        return [], []

    if record.variant_name == "full_framework":
        ranked = sorted(segments, key=lambda item: item.get("importance", 0.0) / max(1, item.get("cost", 1)), reverse=True)
    elif record.variant_name == "multi_agent_no_long_horizon":
        ranked = sorted(
            segments,
            key=lambda item: (0.35 if item["segment_id"] in {"summary", "execution_state", "artifact_rollup"} else item.get("importance", 0.0)) / max(1, item.get("cost", 1)),
            reverse=True,
        )
    elif record.variant_name == "multi_agent_no_compression":
        ranked = list(segments)
    else:
        ranked = sorted(segments, key=lambda item: item.get("importance", 0.0), reverse=True)

    selected = []
    total_cost = 0
    for segment in ranked:
        if total_cost + int(segment.get("cost", 0)) <= budget:
            selected.append(segment)
            total_cost += int(segment.get("cost", 0))
        elif record.variant_name == "multi_agent_no_compression" and total_cost == 0:
            # Simulate a bad first-fit selection in the no-compression baseline.
            selected.append(segment)
            total_cost += int(segment.get("cost", 0))
            break
    selected_ids = {item["segment_id"] for item in selected}
    dropped = [item for item in segments if item["segment_id"] not in selected_ids]
    return selected, dropped


def annotate(record, task, result) -> None:
    selected, dropped = _select_segments(record, task)
    record.metadata["selected_context_segments"] = selected
    record.metadata["dropped_context_segments"] = dropped

    selected_importance = sum(float(item.get("importance", 0.0)) for item in selected)
    total_importance = sum(float(item.get("importance", 0.0)) for item in task.metadata.get("segments", []))
    retained_ratio = len(selected) / max(1, len(selected) + len(dropped))
    coverage = selected_importance / max(1e-6, total_importance)
    budget_limit = int(record.metadata.get("prompt_budget") or record.metadata.get("context_budget_report", {}).get("prompt_char_budget") or 0)
    history_length = int(record.metadata.get("history_length") or 0)
    overflow = sum(int(item.get("cost", 0)) for item in selected) > budget_limit

    model_factor = {
        "mock:strong": 1.0,
        "mock:balanced": 0.92,
        "mock:weak": 0.8,
        "mock:echo": 0.85,
    }.get(record.model_name, 0.9)

    quality = coverage * model_factor
    if record.variant_name == "multi_agent_no_long_horizon":
        quality *= 0.88
    if record.variant_name == "multi_agent_no_compression":
        quality *= 0.78
    if history_length:
        quality *= max(0.72, 1.0 - (history_length - 1) * 0.04)

    record.quality_score = round(min(1.0, quality), 4)
    record.success = record.quality_score >= 0.45
    record.metadata.update(
        {
            "task_success_rate": 1.0 if record.success else 0.0,
            "quality_score": record.quality_score,
            "budget_overflow_ratio": 1.0 if overflow else 0.0,
            "retained_context_ratio": round(retained_ratio, 4),
            "latency": record.latency_ms,
            "token_usage": record.token_usage,
            "context_coverage": round(coverage, 4),
            "history_length": history_length,
        }
    )
