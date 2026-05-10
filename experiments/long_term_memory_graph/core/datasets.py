from __future__ import annotations

import json
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from ..api.models import MemoryCapsuleCandidate
from .schemas import QUESTION_TYPES, ExperimentCase


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _capsule(
    capsule_id: str,
    *,
    created_at: str,
    goal: str,
    summary: str,
    outcome: str,
    task_id: str,
    thread_id: str,
    scope: list[str],
    tags: list[str],
    entities: list[str],
    claims: list[dict[str, Any]] | None = None,
    evidence_refs: list[str] | None = None,
    source_memory_refs: list[str] | None = None,
    confidence: float = 0.86,
    status: str = "validated",
) -> MemoryCapsuleCandidate:
    return MemoryCapsuleCandidate(
        capsule_id=capsule_id,
        thread_id=thread_id,
        task_id=task_id,
        created_at=_dt(created_at),
        goal=goal,
        summary=summary,
        outcome=outcome,
        knowledge_scope=scope,
        tags=tags,
        entities=entities,
        claims=claims or [],
        evidence_refs=evidence_refs or [],
        source_memory_refs=source_memory_refs or [],
        salience_score=0.82,
        confidence=confidence,
        status=status,
    )


def build_default_cases() -> list[ExperimentCase]:
    """构造论文最小完整实验集与专项机制 case。"""

    single = (
        _capsule(
            "cap_retry_policy",
            created_at="2026-03-01T09:00:00Z",
            goal="Stabilize checkout retry policy",
            summary="Checkout payment retries should use exponential backoff at 2s, 4s, and 8s with idempotency keys.",
            outcome="The reusable answer is exponential backoff 2s/4s/8s plus idempotency keys.",
            task_id="checkout:retry",
            thread_id="checkout-run:planner",
            scope=["checkout", "payment"],
            tags=["retry", "backoff", "idempotency"],
            entities=["checkout", "payment_gateway"],
            claims=[{"slot": "retry_policy", "value": "exponential_2_4_8", "scope": "checkout"}],
            evidence_refs=["checkout-log-17"],
        ),
        _capsule(
            "cap_retry_noise",
            created_at="2026-02-20T09:00:00Z",
            goal="Record unrelated UI retry copy",
            summary="The UI copy can say retry later when a coupon service is unavailable.",
            outcome="This memory is unrelated to payment retry policy.",
            task_id="checkout:copy",
            thread_id="checkout-run:writer",
            scope=["checkout", "ui"],
            tags=["copy"],
            entities=["coupon_service"],
            evidence_refs=["ui-note-02"],
            confidence=0.55,
            status="candidate",
        ),
    )

    multi = (
        _capsule(
            "cap_gateway_limit",
            created_at="2026-03-03T10:00:00Z",
            goal="Diagnose API gateway throttling",
            summary="The gateway returned 429 because tenant beta exceeded the 600 rpm burst limit.",
            outcome="Gateway throttling came from tenant beta burst traffic.",
            task_id="ops:tenant-beta",
            thread_id="ops-run:observer",
            scope=["ops", "api_gateway"],
            tags=["rate_limit", "tenant_beta", "incident"],
            entities=["tenant_beta", "api_gateway"],
            claims=[{"slot": "root_cause", "value": "gateway_burst_limit", "scope": "tenant_beta"}],
            evidence_refs=["incident-429", "tenant-beta"],
        ),
        _capsule(
            "cap_queue_mitigation",
            created_at="2026-03-03T10:08:00Z",
            goal="Mitigate tenant beta queue pressure",
            summary="Adding a per-tenant queue and smoothing workers removed the 429 spike without raising the global limit.",
            outcome="The durable mitigation is per-tenant queue smoothing, not a larger global quota.",
            task_id="ops:tenant-beta",
            thread_id="ops-run:planner",
            scope=["ops", "queue", "api_gateway"],
            tags=["rate_limit", "tenant_beta", "queue_smoothing"],
            entities=["tenant_beta", "api_gateway", "worker_queue"],
            claims=[{"slot": "mitigation", "value": "per_tenant_queue_smoothing", "scope": "tenant_beta"}],
            evidence_refs=["incident-429", "worker-queue"],
            source_memory_refs=["cap_gateway_limit"],
        ),
    )

    temporal = (
        _capsule(
            "cap_migration_old",
            created_at="2025-11-02T08:00:00Z",
            goal="Choose billing migration plan",
            summary="The old billing migration plan used one offline batch window.",
            outcome="Old plan: offline batch migration.",
            task_id="billing:migration",
            thread_id="billing-run:planner",
            scope=["billing", "migration"],
            tags=["migration", "old_plan"],
            entities=["billing_db"],
            claims=[{"slot": "migration_plan", "value": "offline_batch", "scope": "billing"}],
            evidence_refs=["migration-v1"],
            confidence=0.45,
            status="deprecated",
        ),
        _capsule(
            "cap_migration_new",
            created_at="2026-03-10T08:00:00Z",
            goal="Choose billing migration plan",
            summary="The current billing migration plan is online dual-write followed by checksum validation.",
            outcome="Current plan: online dual-write with checksum validation.",
            task_id="billing:migration",
            thread_id="billing-run:planner",
            scope=["billing", "migration"],
            tags=["migration", "current_plan", "dual_write"],
            entities=["billing_db"],
            claims=[{"slot": "migration_plan", "value": "online_dual_write_checksum", "scope": "billing"}],
            evidence_refs=["migration-v2"],
            source_memory_refs=["cap_migration_old"],
        ),
    )

    open_domain = (
        _capsule(
            "cap_rollout_policy",
            created_at="2026-03-12T08:30:00Z",
            goal="Define safe rollout policy",
            summary="A safe rollout starts at 5 percent traffic, watches payment errors and latency, then expands after a clean window.",
            outcome="Use 5 percent canary, payment-error and latency guards, and staged expansion.",
            task_id="release:safe-rollout",
            thread_id="release-run:planner",
            scope=["release", "safety"],
            tags=["canary", "guardrail", "latency"],
            entities=["payment_service", "release_pipeline"],
            claims=[{"slot": "rollout_start", "value": "five_percent_canary", "scope": "payment_service"}],
            evidence_refs=["release-guardrails"],
        ),
        _capsule(
            "cap_conflict_bad_rollout",
            created_at="2026-03-12T08:35:00Z",
            goal="Define safe rollout policy",
            summary="A conflicting note suggested moving directly to 100 percent traffic.",
            outcome="This note should be rejected because it conflicts with guardrail policy.",
            task_id="release:safe-rollout",
            thread_id="release-run:assistant",
            scope=["release", "safety"],
            tags=["canary", "conflict"],
            entities=["payment_service", "release_pipeline"],
            claims=[{"slot": "rollout_start", "value": "full_traffic", "scope": "payment_service"}],
            evidence_refs=["release-guardrails"],
            confidence=0.35,
            status="candidate",
        ),
        _capsule(
            "cap_rollback_signal",
            created_at="2026-03-12T08:40:00Z",
            goal="Define rollback signal",
            summary="Rollback is required when payment errors exceed 1 percent for two consecutive windows.",
            outcome="Rollback threshold is payment errors above 1 percent for two windows.",
            task_id="release:safe-rollout",
            thread_id="release-run:observer",
            scope=["release", "safety"],
            tags=["rollback", "guardrail"],
            entities=["payment_service", "release_pipeline"],
            claims=[{"slot": "rollback_signal", "value": "payment_error_gt_1pct_two_windows", "scope": "payment_service"}],
            evidence_refs=["release-guardrails"],
        ),
    )

    scene_match = (
        _capsule(
            "cap_scene_weather",
            created_at="2026-03-14T07:30:00Z",
            goal="Handle city weather summary request",
            summary="Weather planning for Beijing requires checking temperature swing and wind conditions.",
            outcome="Use Beijing weather memory for travel planning.",
            task_id="travel:weather",
            thread_id="travel-run:planner",
            scope=["travel", "weather"],
            tags=["weather", "beijing", "planning"],
            entities=["beijing", "weather_api"],
            evidence_refs=["weather-note-1"],
        ),
        _capsule(
            "cap_scene_finance_noise",
            created_at="2026-03-14T07:32:00Z",
            goal="Summarize finance risk note",
            summary="Finance planning for quarterly margin uses unrelated KPI notes.",
            outcome="This memory should not dominate travel weather retrieval.",
            task_id="finance:risk",
            thread_id="finance-run:planner",
            scope=["finance", "kpi"],
            tags=["finance", "risk"],
            entities=["margin_report"],
            evidence_refs=["finance-note-1"],
        ),
    )

    stale_suppression = (
        _capsule(
            "cap_stale_policy_old",
            created_at="2025-10-01T07:00:00Z",
            goal="Choose incident paging threshold",
            summary="The old paging threshold was 10 minutes for delayed acknowledgements.",
            outcome="Historic threshold only.",
            task_id="ops:paging",
            thread_id="ops-run:pager",
            scope=["ops", "incident"],
            tags=["paging", "threshold"],
            entities=["pagerduty"],
            claims=[{"slot": "ack_threshold", "value": "10_min", "scope": "pager"}],
            evidence_refs=["pager-v1"],
            confidence=0.25,
            status="deprecated",
        ),
        _capsule(
            "cap_stale_policy_new",
            created_at="2026-03-21T07:00:00Z",
            goal="Choose incident paging threshold",
            summary="The current paging threshold is 5 minutes for delayed acknowledgements.",
            outcome="Current threshold is 5 minutes.",
            task_id="ops:paging",
            thread_id="ops-run:pager",
            scope=["ops", "incident"],
            tags=["paging", "threshold"],
            entities=["pagerduty"],
            claims=[{"slot": "ack_threshold", "value": "5_min", "scope": "pager"}],
            evidence_refs=["pager-v2"],
            source_memory_refs=["cap_stale_policy_old"],
        ),
    )

    return [
        ExperimentCase(
            case_id="ltmg_single_retry",
            question_type="Single-hop",
            query="What retry policy should checkout payment use?",
            standard_answer="Use exponential backoff at 2s, 4s, and 8s with idempotency keys.",
            capsules=single,
            target_capsule_ids=("cap_retry_policy",),
            detail_lookup_capsule_ids=("cap_retry_policy",),
            knowledge_scope=("checkout", "payment"),
            tags=("retry", "backoff"),
            entities=("checkout", "payment_gateway"),
            case_tags=("main", "single_hop"),
            token_budget=512,
        ),
        ExperimentCase(
            case_id="ltmg_multi_tenant_beta",
            question_type="Multi-hop",
            query="What caused tenant beta 429 errors and what mitigation should be used?",
            standard_answer="Tenant beta exceeded the API gateway burst limit, and the mitigation is per-tenant queue smoothing rather than raising the global quota.",
            capsules=multi,
            target_capsule_ids=("cap_gateway_limit", "cap_queue_mitigation"),
            target_relation_types=("SAME_TASK", "EVIDENCE_SUPPORTS", "SCOPE_OVERLAP"),
            detail_lookup_capsule_ids=("cap_gateway_limit", "cap_queue_mitigation"),
            knowledge_scope=("ops", "api_gateway", "queue"),
            tags=("tenant_beta", "rate_limit", "queue_smoothing"),
            entities=("tenant_beta", "api_gateway", "worker_queue"),
            case_tags=("main", "multi_hop"),
            token_budget=640,
        ),
        ExperimentCase(
            case_id="ltmg_temporal_migration",
            question_type="Temporal",
            query="What is the current billing migration plan?",
            standard_answer="The current plan is online dual-write followed by checksum validation; the old offline batch plan is deprecated.",
            capsules=temporal,
            target_capsule_ids=("cap_migration_new",),
            target_relation_types=("REVISES", "TEMPORAL_NEXT"),
            revision_target_ids=("cap_migration_new",),
            stale_capsule_ids=("cap_migration_old",),
            detail_lookup_capsule_ids=("cap_migration_new",),
            knowledge_scope=("billing", "migration"),
            tags=("migration", "current_plan"),
            entities=("billing_db",),
            case_tags=("main", "temporal", "revises_case"),
            token_budget=640,
        ),
        ExperimentCase(
            case_id="ltmg_open_rollout",
            question_type="Open Domain",
            query="Summarize the safe rollout guidance for payment service releases.",
            standard_answer="Start with a 5 percent canary, monitor payment errors and latency, expand only after a clean window, and roll back if payment errors exceed 1 percent for two consecutive windows.",
            capsules=open_domain,
            target_capsule_ids=("cap_rollout_policy", "cap_rollback_signal"),
            target_relation_types=("CONFLICTS_WITH", "EVIDENCE_SUPPORTS", "SCOPE_OVERLAP"),
            conflict_loser_ids=("cap_conflict_bad_rollout",),
            detail_lookup_capsule_ids=("cap_rollout_policy", "cap_rollback_signal"),
            knowledge_scope=("release", "safety"),
            tags=("canary", "guardrail", "rollback"),
            entities=("payment_service", "release_pipeline"),
            case_tags=("main", "open_domain", "conflicts_case"),
            token_budget=768,
        ),
        ExperimentCase(
            case_id="ltmg_scene_match_weather",
            question_type="Single-hop",
            query="Which memory should be used for Beijing travel weather planning?",
            standard_answer="Use the Beijing weather planning memory rather than the unrelated finance note.",
            capsules=scene_match,
            target_capsule_ids=("cap_scene_weather",),
            detail_lookup_capsule_ids=("cap_scene_weather",),
            knowledge_scope=("travel", "weather"),
            tags=("weather", "planning"),
            entities=("beijing", "weather_api"),
            case_tags=("mechanism", "scene_match"),
            token_budget=512,
        ),
        ExperimentCase(
            case_id="ltmg_stale_paging_threshold",
            question_type="Temporal",
            query="What is the current incident paging acknowledgement threshold?",
            standard_answer="The current threshold is 5 minutes, and the older 10 minute threshold should be suppressed.",
            capsules=stale_suppression,
            target_capsule_ids=("cap_stale_policy_new",),
            target_relation_types=("REVISES", "TEMPORAL_NEXT"),
            revision_target_ids=("cap_stale_policy_new",),
            stale_capsule_ids=("cap_stale_policy_old",),
            detail_lookup_capsule_ids=("cap_stale_policy_new",),
            knowledge_scope=("ops", "incident"),
            tags=("paging", "threshold"),
            entities=("pagerduty",),
            case_tags=("mechanism", "stale_suppression", "revises_case"),
            token_budget=512,
        ),
    ]


def _case_from_payload(payload: dict[str, Any]) -> ExperimentCase:
    required = ("case_id", "question_type", "query", "standard_answer", "capsules", "target_capsule_ids")
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"Dataset case is missing required fields: {', '.join(missing)}.")
    capsules = tuple(MemoryCapsuleCandidate.model_validate(item) for item in payload["capsules"])
    case = ExperimentCase(
        case_id=str(payload["case_id"]),
        question_type=str(payload["question_type"]),
        query=str(payload["query"]),
        standard_answer=str(payload["standard_answer"]),
        capsules=capsules,
        target_capsule_ids=tuple(payload.get("target_capsule_ids", [])),
        target_relation_types=tuple(payload.get("target_relation_types", [])),
        revision_target_ids=tuple(payload.get("revision_target_ids", [])),
        stale_capsule_ids=tuple(payload.get("stale_capsule_ids", [])),
        conflict_loser_ids=tuple(payload.get("conflict_loser_ids", [])),
        detail_lookup_capsule_ids=tuple(payload.get("detail_lookup_capsule_ids", [])),
        knowledge_scope=tuple(payload.get("knowledge_scope", [])),
        tags=tuple(payload.get("tags", [])),
        entities=tuple(payload.get("entities", [])),
        case_tags=tuple(payload.get("case_tags", [])),
        token_budget=int(payload["token_budget"]) if payload.get("token_budget") is not None else None,
        notes=str(payload.get("notes", "")),
    )
    _validate_case(case)
    return case


def load_cases(
    dataset_path: Path | None = None,
    *,
    case_limit: int | None = None,
    case_offset: int = 0,
    shard_id: int | None = None,
    num_shards: int | None = None,
) -> list[ExperimentCase]:
    if case_limit is not None and case_limit <= 0:
        raise ValueError("case_limit must be > 0 when provided.")
    if case_offset < 0:
        raise ValueError("case_offset must be >= 0.")
    if (shard_id is None) ^ (num_shards is None):
        raise ValueError("shard_id and num_shards must be provided together.")
    if num_shards is not None and num_shards <= 0:
        raise ValueError("num_shards must be > 0 when provided.")
    if shard_id is not None and (shard_id < 0 or (num_shards is not None and shard_id >= num_shards)):
        raise ValueError("shard_id must be within [0, num_shards).")
    if dataset_path is None:
        cases = build_default_cases()
    else:
        path = Path(dataset_path)
        if not path.exists():
            raise FileNotFoundError(f"Dataset path does not exist: {path}")
        rows = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSONL dataset line {line_number}: {exc.msg}") from exc
        cases = [_case_from_payload(item) for item in rows]
    for case in cases:
        _validate_case(case)
    if shard_id is not None and num_shards is not None:
        cases = [case for index, case in enumerate(cases) if index % num_shards == shard_id]
    if case_offset:
        cases = cases[case_offset:]
    if case_limit is not None:
        return cases[:case_limit]
    return cases


def _validate_case(case: ExperimentCase) -> None:
    if case.question_type not in QUESTION_TYPES:
        raise ValueError(f"Unsupported question_type for {case.case_id}: {case.question_type}.")
    if not case.capsules:
        raise ValueError(f"Experiment case {case.case_id} must contain at least one memory capsule.")
    capsule_ids = {capsule.capsule_id for capsule in case.capsules}
    for field_name, ids in (
        ("target_capsule_ids", case.target_capsule_ids),
        ("revision_target_ids", case.revision_target_ids),
        ("stale_capsule_ids", case.stale_capsule_ids),
        ("conflict_loser_ids", case.conflict_loser_ids),
        ("detail_lookup_capsule_ids", case.detail_lookup_capsule_ids),
    ):
        missing = sorted(set(ids) - capsule_ids)
        if missing:
            raise ValueError(f"Experiment case {case.case_id} has unknown {field_name}: {', '.join(missing)}.")
