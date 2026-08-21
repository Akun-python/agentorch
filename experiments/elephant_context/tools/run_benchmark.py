from __future__ import annotations

import argparse

from ..benchmarks.chapter_benchmark import run_elephant_benchmark_sync
from ..core.env_config import is_probe_backend, validate_live_backend_env


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("benchmark", help="Run the local MGCM chapter benchmark package.")
    parser.add_argument(
        "--suite",
        choices=["full", "context", "lifecycle"],
        default="full",
        help="Benchmark suite to run. Defaults to the full MGCM chapter package.",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run a smoke subset: 5 context cases with two context variants and 5 lifecycle cases with two lifecycle variants.",
    )
    parser.add_argument("--output-dir", type=str, default=None, help="Optional artifact output directory.")
    parser.add_argument("--variants", nargs="*", default=None, help="Variant names to run.")
    parser.add_argument("--budgets", nargs="*", type=int, default=None, help="Character budgets to run.")
    parser.add_argument("--cases", nargs="*", default=None, help="Specific benchmark case IDs to run.")
    parser.add_argument(
        "--model-backend",
        choices=["probe", "openai", "local-llm"],
        default="probe",
        help="Model backend for benchmark runs. probe is deterministic local baseline.",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Dataset identifier. Examples: context_synth, lifecycle_synth, real_task_x.",
    )
    parser.add_argument(
        "--seeds",
        nargs="*",
        type=int,
        default=None,
        help="Random seeds for repeated runs and confidence estimates.",
    )
    parser.add_argument(
        "--report-level",
        choices=["brief", "full"],
        default="full",
        help="Artifact verbosity. brief keeps compact traces; full keeps detailed traces.",
    )
    parser.set_defaults(handler=_handle)


def _handle(args: argparse.Namespace):
    env_report = None
    if not is_probe_backend(str(args.model_backend)):
        env_report = validate_live_backend_env(model_backend=str(args.model_backend))
    result = run_elephant_benchmark_sync(
        suite=args.suite,
        quick=bool(args.quick),
        output_dir=args.output_dir,
        variants=args.variants,
        budgets=args.budgets,
        case_ids=args.cases,
        model_backend=str(args.model_backend),
        dataset=args.dataset,
        seeds=args.seeds,
        report_level=str(args.report_level),
    )
    if env_report is not None:
        result["env_report"] = {
            "env_file": env_report.env_file,
            "env_file_exists": env_report.env_file_exists,
            "loaded": env_report.loaded,
            "model_backend": env_report.model_backend,
            "api_key_present": env_report.api_key_present,
            "base_url_present": env_report.base_url_present,
            "model_present": env_report.model_present,
        }
    return result
