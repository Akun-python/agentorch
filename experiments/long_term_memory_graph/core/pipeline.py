from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .agentorch_runtime import AgentTorchExperimentRunner
from .artifacts import write_artifacts
from .datasets import load_cases
from .efficiency import build_efficiency_payload, build_scale_tier_payload
from .judge import ExperimentJudgeRunner, judge_answer, serialize_judge_raw
from .methods import ExperimentMethodRunner
from .resume import build_completed_key_set, load_existing_records
from .schemas import (
    ABLATION_VARIANTS,
    CORE_LOCAL_BASELINE_METHODS,
    MAIN_METHOD,
    PROXY_EXTENSION_METHODS,
    SUPPORTED_BASELINE_METHODS,
    ExperimentRecord,
    ExperimentRunConfig,
    ExperimentSuiteResult,
)
from .statistics import aggregate_records, attach_relative_tokens


def run_suite(config: ExperimentRunConfig) -> ExperimentSuiteResult:
    _validate_run_config(config)
    cases = load_cases(
        config.dataset_path,
        case_limit=config.case_limit,
        case_offset=config.case_offset,
        shard_id=config.shard_id,
        num_shards=config.num_shards,
    )
    if not cases:
        raise ValueError("Experiment suite requires at least one case.")
    method_runner = ExperimentMethodRunner(
        top_candidates=config.top_candidates,
        top_seeds=config.top_seeds,
        max_nodes=config.max_nodes,
        max_edges=config.max_edges,
        seed=config.seed,
        embedding_model=config.embedding_model,
        embedding_dimensions=config.embedding_dimensions,
    )
    agent_runner = AgentTorchExperimentRunner(
        model_backend=config.model_backend,
        model_name=config.model_name,
        env_file=str(config.env_file) if config.env_file is not None else None,
        load_env=config.load_env,
        overwrite_env=config.overwrite_env,
    )
    judge_runner = ExperimentJudgeRunner(
        judge_backend=config.judge_backend,
        judge_model_backend=config.judge_model_backend,
        judge_model_name=config.judge_model_name,
        env_file=str(config.env_file) if config.env_file is not None else None,
        load_env=config.load_env,
        overwrite_env=config.overwrite_env,
    )
    allowed_pairs = {_resolve_method_and_variant(config.suite, method) for method in config.methods}
    existing_records = (
        load_existing_records(
            output_dir=config.output_dir,
            suite=config.suite,
            allowed_method_variants=allowed_pairs,
            allowed_case_ids={case.case_id for case in cases},
            max_run_round=config.runs,
        )
        if config.resume
        else []
    )
    completed_keys = build_completed_key_set(existing_records)
    planned_record_count = len(cases) * len(config.methods) * config.runs
    records: list[ExperimentRecord] = list(existing_records)
    for run_round in range(1, config.runs + 1):
        for case in cases:
            for method in config.methods:
                retrieval_method, variant = _resolve_method_and_variant(config.suite, method)
                record_key = (case.case_id, retrieval_method, variant, run_round)
                if record_key in completed_keys:
                    continue
                retrieval = method_runner.run(case, method=retrieval_method, variant=variant)
                answer = agent_runner.answer(case=case, retrieval=retrieval, run_round=run_round)
                judge = judge_answer(
                    case=case,
                    retrieval=retrieval,
                    answer=answer,
                    judge_backend=config.judge_backend,
                    judge_runner=judge_runner,
                )
                record = _build_record(
                    suite=config.suite,
                    case=case,
                    retrieval=retrieval,
                    answer=answer,
                    judge_score=judge.score,
                    judge_raw_output=serialize_judge_raw(judge),
                    judge_backend=config.judge_backend,
                    run_round=run_round,
                )
                records.append(record)
                completed_keys.add(record_key)

    token_reference_method = _select_token_reference_method(config.suite, records)
    attach_relative_tokens(records, reference_method=token_reference_method)
    aggregates = aggregate_records(records, bootstrap_samples=config.bootstrap_samples)
    if not any(record.method == token_reference_method for record in records):
        token_reference_method = "suite_mean"

    manual_review_rows = _build_manual_review_rows(records, limit=config.manual_review_sample_size)
    second_judge_rows = _build_second_judge_rows(records, limit=config.second_judge_sample_size)
    parameter_sweep_rows = _build_parameter_sweep_rows(config) if config.suite == "ablation" else []
    efficiency_payload = build_efficiency_payload(records) if config.suite == "main" else {}
    scale_tier_payload = build_scale_tier_payload(cases) if config.suite == "main" else {}

    manifest: dict[str, Any] = {
        "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "suite": config.suite,
        "methods": list(config.methods),
        "case_count": len(cases),
        "selected_case_ids": [case.case_id for case in cases],
        "case_offset": config.case_offset,
        "shard_id": config.shard_id,
        "num_shards": config.num_shards,
        "runs": config.runs,
        "seed": config.seed,
        "dataset_path": str(config.dataset_path) if config.dataset_path else "built_in_locomo_style_probe",
        "resume_enabled": config.resume,
        "planned_record_count": planned_record_count,
        "resumed_record_count": len(existing_records),
        "pending_record_count": max(0, planned_record_count - len(existing_records)),
        "judge_backend": config.judge_backend,
        "judge_model_backend": config.judge_model_backend,
        "judge_model_name": config.judge_model_name,
        "model_backend": config.model_backend,
        "model_name": config.model_name,
        "embedding_model": config.embedding_model,
        "embedding_dimensions": config.embedding_dimensions,
        "env_file": str(config.env_file) if config.env_file is not None else None,
        "load_env": config.load_env,
        "env_loaded": agent_runner.env_report.loaded if agent_runner.env_report is not None else False,
        "env_file_exists": agent_runner.env_report.env_file_exists if agent_runner.env_report is not None else False,
        "env_api_key_present": agent_runner.env_report.api_key_present if agent_runner.env_report is not None else False,
        "env_base_url_present": agent_runner.env_report.base_url_present if agent_runner.env_report is not None else False,
        "env_model_present": agent_runner.env_report.model_present if agent_runner.env_report is not None else False,
        "env_checked": agent_runner.env_report is not None,
        "judge_env_loaded": judge_runner.env_report.loaded if judge_runner.env_report is not None else False,
        "judge_env_file_exists": judge_runner.env_report.env_file_exists if judge_runner.env_report is not None else False,
        "judge_env_api_key_present": judge_runner.env_report.api_key_present if judge_runner.env_report is not None else False,
        "judge_env_base_url_present": judge_runner.env_report.base_url_present if judge_runner.env_report is not None else False,
        "judge_env_model_present": judge_runner.env_report.model_present if judge_runner.env_report is not None else False,
        "record_count": len(records),
        "aggregate_count": len(aggregates),
        "token_reference_method": token_reference_method,
        "bootstrap_samples": config.bootstrap_samples,
        "manual_review_sample_size": len(manual_review_rows),
        "second_judge_sample_size": len(second_judge_rows),
        "parameter_sweep_count": len(parameter_sweep_rows),
        "efficiency_report_enabled": config.suite == "main",
        "output_dir": str(config.output_dir.resolve()),
        "required_csv_fields": [
            "case_id",
            "question_type",
            "method",
            "source_boundary",
            "is_proxy",
            "answer",
            "standard_answer",
            "judge_score",
            "judge_raw_output",
            "target_capsule_hit",
            "target_relation_hit",
            "input_tokens",
            "output_tokens",
            "returned_node_count",
            "returned_edge_count",
            "latency_ms",
            "run_round",
        ],
    }
    if config.protocol_metadata:
        manifest["protocol"] = config.protocol_metadata
    if config.suite == "comparison":
        selected_proxy = [method for method in config.methods if method in PROXY_EXTENSION_METHODS]
        manifest["include_proxy_extension"] = bool(selected_proxy)
        manifest["proxy_extension_selected_methods"] = selected_proxy
    artifact_paths = write_artifacts(
        output_dir=config.output_dir,
        suite=config.suite,
        records=records,
        aggregates=aggregates,
        manifest=manifest,
        manual_review_rows=manual_review_rows,
        second_judge_rows=second_judge_rows,
        parameter_sweep_rows=parameter_sweep_rows,
        efficiency_payload=efficiency_payload,
        scale_tier_payload=scale_tier_payload,
    )
    manifest["artifact_paths"] = artifact_paths
    return ExperimentSuiteResult(manifest=manifest, records=records, aggregates=aggregates)


def _validate_run_config(config: ExperimentRunConfig) -> None:
    if config.runs <= 0:
        raise ValueError("runs must be > 0.")
    if config.case_limit is not None and config.case_limit <= 0:
        raise ValueError("case_limit must be > 0 when provided.")
    if config.case_offset < 0:
        raise ValueError("case_offset must be >= 0.")
    if (config.shard_id is None) ^ (config.num_shards is None):
        raise ValueError("shard_id and num_shards must be provided together.")
    if config.num_shards is not None and config.num_shards <= 0:
        raise ValueError("num_shards must be > 0 when provided.")
    if config.shard_id is not None and (config.shard_id < 0 or (config.num_shards is not None and config.shard_id >= config.num_shards)):
        raise ValueError("shard_id must be within [0, num_shards).")
    if not config.methods:
        raise ValueError("Experiment suite requires at least one method or ablation variant.")

    allowed_by_suite = {
        "main": {MAIN_METHOD},
        "comparison": set(SUPPORTED_BASELINE_METHODS),
        "ablation": set(ABLATION_VARIANTS),
    }
    if config.suite not in allowed_by_suite:
        raise ValueError(f"Unsupported experiment suite: {config.suite}.")
    unknown = sorted(set(config.methods) - allowed_by_suite[config.suite])
    if unknown:
        raise ValueError(f"Unsupported {config.suite} method or variant: {', '.join(unknown)}.")


def _select_token_reference_method(suite: str, records: list[ExperimentRecord]) -> str:
    methods = {record.method for record in records}
    if suite == "comparison":
        if all(record.source_boundary == "proxy" for record in records):
            if "mem0_memory" in methods:
                return "mem0_memory"
        if "no_long_term_memory" in methods:
            return "no_long_term_memory"
        if "mem0_memory" in methods:
            return "mem0_memory"
    if "no_long_term_memory" in methods:
        return "no_long_term_memory"
    return "suite_mean"


def _resolve_method_and_variant(suite: str, method: str) -> tuple[str, str]:
    if suite == "ablation":
        return "clarks_nutcracker_graph", method
    return method, "full"


def _source_boundary_for_method(method: str) -> tuple[str, bool]:
    if method in CORE_LOCAL_BASELINE_METHODS or method == MAIN_METHOD:
        return ("core_local", False)
    if method in PROXY_EXTENSION_METHODS:
        return ("proxy", True)
    return ("literature_only", False)


def _build_record(
    *,
    suite: str,
    case,
    retrieval,
    answer,
    judge_score: float,
    judge_raw_output: str,
    judge_backend: str,
    run_round: int,
) -> ExperimentRecord:
    returned_capsules = set(retrieval.returned_capsule_ids)
    target_capsules = set(case.target_capsule_ids)
    target_relations = set(case.target_relation_types)
    returned_relations = set(retrieval.returned_relation_types)
    stale_returned = returned_capsules.intersection(case.stale_capsule_ids)
    conflict_returned = returned_capsules.intersection(case.conflict_loser_ids)
    target_capsule_hit = bool(target_capsules) and target_capsules.issubset(returned_capsules)
    target_relation_hit = not target_relations or bool(target_relations.intersection(returned_relations))
    evidence_completeness = len(target_capsules.intersection(returned_capsules)) / max(1, len(target_capsules))
    capsule_recall_at_k = evidence_completeness
    revision_target_ids = set(case.revision_target_ids)
    revision_hit_rate = len(revision_target_ids.intersection(returned_capsules)) / max(1, len(revision_target_ids)) if revision_target_ids else 1.0
    stale_rate = len(stale_returned) / max(1, len(returned_capsules))
    conflict_success = 1.0 if not case.conflict_loser_ids or not conflict_returned else 0.0
    usefulness = (
        float(target_capsule_hit)
        + float(target_relation_hit)
        + evidence_completeness
        + revision_hit_rate
        + (1.0 - stale_rate)
        + conflict_success
    ) / 6.0
    source_boundary, is_proxy = _source_boundary_for_method(retrieval.method)
    returned_evidence_count = sum(1 for edge in retrieval.returned_edge_keys if "EVIDENCE_SUPPORTS" in edge)
    return ExperimentRecord(
        suite=suite,
        case_id=case.case_id,
        question_type=case.question_type,
        method=retrieval.method,
        variant=retrieval.variant,
        source_boundary=source_boundary,
        is_proxy=is_proxy,
        answer=answer.answer,
        standard_answer=case.standard_answer,
        judge_score=judge_score,
        judge_raw_output=judge_raw_output,
        target_capsule_hit=target_capsule_hit,
        target_relation_hit=target_relation_hit,
        input_tokens=answer.input_tokens,
        output_tokens=answer.output_tokens,
        returned_node_count=len(retrieval.returned_capsule_ids),
        returned_edge_count=len(retrieval.returned_edge_keys),
        latency_ms=round(retrieval.latency_ms, 4),
        run_round=run_round,
        judge_backend=judge_backend,
        agentorch_run_id=answer.agentorch_run_id,
        thread_id=answer.thread_id,
        returned_capsule_ids=json.dumps(retrieval.returned_capsule_ids, ensure_ascii=False),
        returned_relation_types=json.dumps(retrieval.returned_relation_types, ensure_ascii=False),
        suppressed_stale_nodes=json.dumps(retrieval.suppressed_stale_nodes, ensure_ascii=False),
        suppressed_conflict_nodes=json.dumps(retrieval.suppressed_conflict_nodes, ensure_ascii=False),
        case_tags=json.dumps(list(case.case_tags), ensure_ascii=False),
        detail_lookup_capsule_ids=json.dumps(retrieval.detail_lookup_capsule_ids, ensure_ascii=False),
        latency_breakdown_json=json.dumps(retrieval.latency_breakdown, ensure_ascii=False, sort_keys=True),
        stale_node_injection_rate=round(stale_rate, 4),
        conflict_resolution_success=round(conflict_success, 4),
        evidence_completeness=round(evidence_completeness, 4),
        capsule_recall_at_k=round(capsule_recall_at_k, 4),
        revision_hit_rate=round(revision_hit_rate, 4),
        returned_memory_usefulness=round(usefulness, 4),
        returned_evidence_count=returned_evidence_count,
        detail_lookup_latency_ms=round(retrieval.detail_lookup_latency_ms, 4),
        detail_lookup_hit_count=retrieval.detail_lookup_hit_count,
        detail_lookup_missing_count=retrieval.detail_lookup_missing_count,
    )


def _build_manual_review_rows(records: list[ExperimentRecord], *, limit: int) -> list[dict[str, Any]]:
    rows = []
    for record in records[: max(0, limit)]:
        rows.append(
            {
                "case_id": record.case_id,
                "method": record.method,
                "variant": record.variant,
                "answer": record.answer,
                "standard_answer": record.standard_answer,
                "judge_score": record.judge_score,
                "judge_raw_output": record.judge_raw_output,
            }
        )
    return rows


def _build_second_judge_rows(records: list[ExperimentRecord], *, limit: int) -> list[dict[str, Any]]:
    rows = []
    for record in records[: max(0, limit)]:
        rows.append(
            {
                "case_id": record.case_id,
                "method": record.method,
                "variant": record.variant,
                "source_boundary": record.source_boundary,
                "answer": record.answer,
                "standard_answer": record.standard_answer,
                "returned_capsule_ids": record.returned_capsule_ids,
                "returned_relation_types": record.returned_relation_types,
            }
        )
    return rows


def _build_parameter_sweep_rows(config: ExperimentRunConfig) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, values in (config.sweep_parameters or {}).items():
        for value in values:
            rows.append({"parameter": name, "value": value, "suite": config.suite})
    return rows
