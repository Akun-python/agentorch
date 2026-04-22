from __future__ import annotations

import argparse

from ..chapter_benchmark import run_elephant_benchmark_sync


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("benchmark", help="Run the local elephant-context benchmark matrix.")
    parser.add_argument(
        "--suite",
        choices=["full", "context", "lifecycle"],
        default="full",
        help="Benchmark suite to run. Defaults to the full MGCM chapter package.",
    )
    parser.add_argument("--quick", action="store_true", help="Run the 5-case smoke subset with two variants at budget 12000.")
    parser.add_argument("--output-dir", type=str, default=None, help="Optional artifact output directory.")
    parser.add_argument("--variants", nargs="*", default=None, help="Variant names to run.")
    parser.add_argument("--budgets", nargs="*", type=int, default=None, help="Character budgets to run.")
    parser.add_argument("--cases", nargs="*", default=None, help="Specific benchmark case IDs to run.")
    parser.set_defaults(handler=_handle)


def _handle(args: argparse.Namespace):
    return run_elephant_benchmark_sync(
        suite=args.suite,
        quick=bool(args.quick),
        output_dir=args.output_dir,
        variants=args.variants,
        budgets=args.budgets,
        case_ids=args.cases,
    )
