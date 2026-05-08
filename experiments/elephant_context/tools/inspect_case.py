from __future__ import annotations

import argparse

from ..benchmarks.chapter_benchmark import inspect_elephant_case_sync
from ..core.env_config import is_probe_backend, validate_live_backend_env


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
    env_report = None
    if not is_probe_backend(str(args.model_backend)):
        env_report = validate_live_backend_env(model_backend=str(args.model_backend))
    result = inspect_elephant_case_sync(
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
