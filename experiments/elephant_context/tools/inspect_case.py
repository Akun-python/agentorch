from __future__ import annotations

import argparse

from ..benchmarks.chapter_benchmark import inspect_elephant_case_sync


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
    parser.add_argument(
        "--model-backend",
        choices=["probe", "openai", "local-llm"],
        default="probe",
        help="Model backend for inspection.",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Dataset identifier. Examples: context_synth, lifecycle_synth, real_task_x.",
    )
    parser.add_argument("--seed", type=int, default=0, help="Random seed for inspection run.")
    parser.add_argument(
        "--report-level",
        choices=["brief", "full"],
        default="full",
        help="Inspection verbosity level.",
    )
    parser.add_argument("--output-dir", type=str, default=None, help="Optional artifact output directory.")
    parser.set_defaults(handler=_handle)


def _handle(args: argparse.Namespace):
    return inspect_elephant_case_sync(
        suite=args.suite,
        case_id=args.case_id,
        variant=args.variant,
        budget=int(args.budget),
        model_backend=str(args.model_backend),
        dataset=args.dataset,
        seed=int(args.seed),
        report_level=str(args.report_level),
        output_dir=args.output_dir,
    )
