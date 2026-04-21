from __future__ import annotations

import json
from pathlib import Path

from .config import TaskSpec
from experiments.formal.ingestion import resolve_benchmark_split


def load_tasks(path: Path) -> list[TaskSpec]:
    tasks: list[TaskSpec] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        tasks.append(TaskSpec.model_validate(json.loads(line)))
    return tasks


def load_formal_tasks(benchmark_ids: list[str], *, split: str = "official_subset") -> list[TaskSpec]:
    tasks: list[TaskSpec] = []
    for benchmark_id in benchmark_ids:
        path = resolve_benchmark_split(benchmark_id, split=split)
        tasks.extend(load_tasks(path))
    return tasks
