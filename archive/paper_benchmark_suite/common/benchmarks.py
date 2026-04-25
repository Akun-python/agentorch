from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BENCHMARK_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "tasks" / "benchmark_registry.json"


def load_benchmark_registry(path: Path | None = None) -> dict[str, Any]:
    registry_path = path or BENCHMARK_REGISTRY_PATH
    if not registry_path.exists():
        return {"benchmarks": {}, "rq_mapping": {}}
    return json.loads(registry_path.read_text(encoding="utf-8"))


def get_benchmark_definition(benchmark_id: str | None) -> dict[str, Any] | None:
    if not benchmark_id:
        return None
    registry = load_benchmark_registry()
    return registry.get("benchmarks", {}).get(benchmark_id)


def list_rq_benchmarks(experiment_name: str) -> list[dict[str, Any]]:
    registry = load_benchmark_registry()
    benchmark_ids = registry.get("rq_mapping", {}).get(experiment_name, [])
    return [registry.get("benchmarks", {}).get(item, {"benchmark_id": item}) for item in benchmark_ids]
