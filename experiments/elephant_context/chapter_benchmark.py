from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .benchmark import inspect_elephant_context_case_sync, run_elephant_context_benchmark_sync
from .lifecycle_benchmark import inspect_lifecycle_case_sync, run_lifecycle_benchmark_sync


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _split_variants(variants: list[str] | None) -> tuple[list[str] | None, list[str] | None]:
    if not variants:
        return None, None
    context_variants = [item for item in variants if item.startswith("elephant_") or item in {"multi_agent_default_context", "single_agent_long_context", "full_framework", "multi_agent_no_elephant"}]
    lifecycle_variants = [item for item in variants if item.startswith("mgcm_")]
    return context_variants, lifecycle_variants


def _split_cases(case_ids: list[str] | None) -> tuple[list[str] | None, list[str] | None]:
    if not case_ids:
        return None, None
    context_cases = [item for item in case_ids if not item.startswith(("succession_", "cross_thread_", "promotion_validation_", "conflict_", "temporal_decay_"))]
    lifecycle_cases = [item for item in case_ids if item.startswith(("succession_", "cross_thread_", "promotion_validation_", "conflict_", "temporal_decay_"))]
    return context_cases, lifecycle_cases


def _should_run_split_suite(
    *,
    suite: str,
    target: str,
    variants: list[str] | None,
    cases: list[str] | None,
) -> bool:
    if suite == target:
        return True
    if suite != "full":
        return False
    if variants is not None and not variants:
        return False
    if cases is not None and not cases:
        return False
    return True


def run_elephant_benchmark_sync(
    *,
    suite: str = "full",
    quick: bool = False,
    output_dir: str | Path | None = None,
    variants: list[str] | None = None,
    budgets: list[int] | None = None,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    run_dir = Path(output_dir) if output_dir is not None else (Path("artifacts") / "elephant_context_benchmark" / __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S"))
    run_dir.mkdir(parents=True, exist_ok=True)
    context_variants, lifecycle_variants = _split_variants(variants)
    context_cases, lifecycle_cases = _split_cases(case_ids)
    run_context = _should_run_split_suite(
        suite=suite,
        target="context",
        variants=context_variants if variants is not None else None,
        cases=context_cases if case_ids is not None else None,
    )
    run_lifecycle = _should_run_split_suite(
        suite=suite,
        target="lifecycle",
        variants=lifecycle_variants if variants is not None else None,
        cases=lifecycle_cases if case_ids is not None else None,
    )
    if suite == "full" and not (run_context or run_lifecycle):
        raise ValueError("No benchmark suites matched the provided full-suite variant/case filters.")
    manifest: dict[str, Any] = {
        "run_id": run_dir.name,
        "suite": suite,
        "quick": quick,
        "output_dir": str(run_dir.resolve()),
    }
    summary_sections = [
        "# MGCM Chapter Benchmark Summary",
        "",
        f"- Run ID: `{run_dir.name}`",
        f"- Suite: `{suite}`",
        f"- Output Dir: `{run_dir.resolve()}`",
        "- Context artifacts: `context/`",
        "- Lifecycle artifacts: `lifecycle/`",
        "",
    ]
    combined_runs_path = run_dir / "runs.jsonl"
    combined_runs: list[str] = []

    if run_context:
        context_dir = run_dir / "context"
        context_manifest = run_elephant_context_benchmark_sync(
            quick=quick,
            output_dir=context_dir,
            variants=context_variants if suite == "full" else variants,
            budgets=budgets,
            case_ids=context_cases if suite == "full" else case_ids,
        )
        manifest["context"] = context_manifest
        context_runs = _read_text(context_dir / "runs.jsonl")
        if context_runs:
            combined_runs.append(context_runs.rstrip())
        summary_sections.extend(
            [
                "## Context Suite",
                "",
                _read_text(context_dir / "summary.md") or "_Context suite summary missing._",
                "",
            ]
        )

    if run_lifecycle:
        lifecycle_dir = run_dir / "lifecycle"
        lifecycle_manifest = run_lifecycle_benchmark_sync(
            quick=quick,
            output_dir=lifecycle_dir,
            variants=lifecycle_variants if suite == "full" else variants,
            case_ids=lifecycle_cases if suite == "full" else case_ids,
        )
        manifest["lifecycle"] = lifecycle_manifest
        lifecycle_runs = _read_text(lifecycle_dir / "runs.jsonl")
        if lifecycle_runs:
            combined_runs.append(lifecycle_runs.rstrip())
        summary_sections.extend(
            [
                "## Lifecycle Suite",
                "",
                _read_text(lifecycle_dir / "summary.md") or "_Lifecycle suite summary missing._",
                "",
            ]
        )

    if combined_runs:
        combined_runs_path.write_text("\n".join(combined_runs) + "\n", encoding="utf-8")
    summary_path = run_dir / "summary.md"
    summary_path.write_text("\n".join(summary_sections).strip() + "\n", encoding="utf-8")
    _write_json(run_dir / "manifest.json", manifest)
    return manifest


def inspect_elephant_case_sync(
    *,
    suite: str = "context",
    case_id: str,
    variant: str | None = None,
    budget: int = 12000,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    if suite == "context":
        return inspect_elephant_context_case_sync(
            case_id=case_id,
            variant=variant or "elephant_full",
            budget=budget,
            output_dir=output_dir,
        )
    if suite == "lifecycle":
        return inspect_lifecycle_case_sync(
            case_id=case_id,
            variant=variant or "mgcm_full",
            output_dir=output_dir,
        )
    raise ValueError("inspect-case only supports suite='context' or suite='lifecycle'.")


__all__ = ["inspect_elephant_case_sync", "run_elephant_benchmark_sync"]
