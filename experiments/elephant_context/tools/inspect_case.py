from __future__ import annotations

import argparse

from ..chapter_benchmark import inspect_elephant_case_sync


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("inspect-case", help="Run a single elephant-context case and write an inspection artifact.")
    parser.add_argument(
        "--suite",
        choices=["context", "lifecycle"],
        default="context",
        help="Inspection suite to run.",
    )
    parser.add_argument("--case-id", required=True, help="Benchmark case ID.")
    parser.add_argument("--variant", default=None, help="Variant name. Defaults depend on suite.")
    parser.add_argument("--budget", type=int, default=12000, help="Character budget.")
    parser.add_argument("--output-dir", type=str, default=None, help="Optional artifact output directory.")
    parser.set_defaults(handler=_handle)


def _handle(args: argparse.Namespace):
    return inspect_elephant_case_sync(
        suite=args.suite,
        case_id=args.case_id,
        variant=args.variant,
        budget=int(args.budget),
        output_dir=args.output_dir,
    )
