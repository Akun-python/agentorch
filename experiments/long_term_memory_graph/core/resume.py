from __future__ import annotations

import json
from pathlib import Path

from .schemas import ExperimentRecord

CompletedRecordKey = tuple[str, str, str, int]


def load_existing_records(
    *,
    output_dir: Path,
    suite: str,
    allowed_method_variants: set[tuple[str, str]],
    allowed_case_ids: set[str],
    max_run_round: int,
) -> list[ExperimentRecord]:
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        existing_suite = payload.get("suite")
        if existing_suite and existing_suite != suite:
            raise ValueError(f"Resume output_dir contains a different suite: {existing_suite} != {suite}.")

    runs_path = output_dir / "runs.jsonl"
    if not runs_path.exists():
        return []

    deduped: dict[CompletedRecordKey, ExperimentRecord] = {}
    for line_number, line in enumerate(runs_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid resume runs.jsonl line {line_number}: {exc.msg}") from exc
        record = ExperimentRecord(**payload)
        key = build_completed_record_key(record)
        if record.suite != suite:
            continue
        if record.case_id not in allowed_case_ids:
            continue
        if (record.method, record.variant) not in allowed_method_variants:
            continue
        if record.run_round > max_run_round:
            continue
        deduped[key] = record
    return [deduped[key] for key in sorted(deduped, key=lambda item: (item[3], item[0], item[1], item[2]))]


def build_completed_record_key(record: ExperimentRecord) -> CompletedRecordKey:
    return (record.case_id, record.method, record.variant, record.run_round)


def build_completed_key_set(records: list[ExperimentRecord]) -> set[CompletedRecordKey]:
    return {build_completed_record_key(record) for record in records}
