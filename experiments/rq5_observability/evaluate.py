from __future__ import annotations


def annotate(record, task, result) -> None:
    todo_summary = record.todo_summary or {}
    record.metadata.update(
        {
            "trace_coverage": 1.0 if record.sqlite_path else 0.0,
            "failure_localization_accuracy": 1.0 if (record.sqlite_path and record.status in {"failed", "completed", "waiting_human"}) else 0.0,
            "todo_consistency": 1.0 if todo_summary else 0.0,
            "diagnostic_time_seconds": round(record.latency_ms / 1000.0, 4),
            "diagnostic_accuracy": 1.0 if record.sqlite_path else 0.0,
        }
    )
