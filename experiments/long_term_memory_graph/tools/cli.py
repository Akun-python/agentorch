from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from . import (
    backfill_sqlite,
    benchmark_baseline_stability,
    benchmark_baselines,
    benchmark_graph_scale_latency,
    benchmark_latency,
    generate_paper_tables,
    seed_demo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m experiments.long_term_memory_graph",
        description="Utility entrypoints for the long-term memory graph experiment module.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    seed_demo.build_parser(subparsers)
    benchmark_latency.build_parser(subparsers)
    benchmark_baselines.build_parser(subparsers)
    benchmark_baseline_stability.build_parser(subparsers)
    benchmark_graph_scale_latency.build_parser(subparsers)
    generate_paper_tables.build_parser(subparsers)
    backfill_sqlite.build_parser(subparsers)
    return parser


def _serialize(result: Any) -> str:
    if isinstance(result, BaseModel):
        payload: Any = result.model_dump()
    else:
        payload = result
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = args.handler(args)
    if result is not None:
        print(_serialize(result))
    return 0


__all__ = ["build_parser", "main"]
