from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from . import inspect_case, run_benchmark


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m experiments.elephant_context",
        description="Utility entrypoints for the elephant-context chapter experiment package.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_benchmark.build_parser(subparsers)
    inspect_case.build_parser(subparsers)
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
