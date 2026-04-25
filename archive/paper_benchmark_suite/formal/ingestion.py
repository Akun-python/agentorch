from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FORMAL_ROOT = Path(__file__).resolve().parent
BUNDLED_ROOT = FORMAL_ROOT / "bundled"
CACHE_ROOT = FORMAL_ROOT / "cache"
REGISTRY_PATH = FORMAL_ROOT / "registry.json"


def load_formal_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def resolve_benchmark_split(benchmark_id: str, split: str = "official_subset") -> Path:
    registry = load_formal_registry()
    benchmark = registry["benchmarks"][benchmark_id]
    split_meta = benchmark["splits"][split]

    cache_path = CACHE_ROOT / benchmark_id / f"{split}.jsonl"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        return cache_path

    bundled_path = BUNDLED_ROOT / split_meta["bundled_path"]
    if not bundled_path.exists():
        raise FileNotFoundError(f"Bundled split not found for {benchmark_id}/{split}: {bundled_path}")

    cache_path.write_text(bundled_path.read_text(encoding="utf-8"), encoding="utf-8")
    return cache_path
