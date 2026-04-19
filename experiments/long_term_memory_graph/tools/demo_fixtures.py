from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import timedelta

from agentorch.knowledge.base import EmbeddingProvider

from ..api.models import MemoryCapsuleCandidate, RecallRequest
from ..domain.utils import now_utc


@dataclass(frozen=True)
class ScenarioSpec:
    code: str
    goal: str
    asset: str
    owner: str
    domain: str
    scope: str
    artifact: str
    action: str
    risk: str
    primary_slot: str
    entities: tuple[str, ...]
    tags: tuple[str, ...]
    knowledge_scope: tuple[str, ...]
    query: str


SCENARIOS: tuple[ScenarioSpec, ...] = (
    ScenarioSpec(
        code="deploy_alpha_prod",
        goal="Stabilize service alpha production deployment",
        asset="service alpha",
        owner="alice",
        domain="deployment",
        scope="prod",
        artifact="release runbook",
        action="production rollout",
        risk="owner approval",
        primary_slot="deployment_state",
        entities=("service_alpha", "owner_alice", "cluster_north"),
        tags=("deploy", "approval", "prod", "alpha"),
        knowledge_scope=("deployment", "release", "approval", "operations"),
        query="service alpha deployment alice approval production rollout",
    ),
    ScenarioSpec(
        code="deploy_beta_staging",
        goal="Stabilize service beta staging release",
        asset="service beta",
        owner="bob",
        domain="deployment",
        scope="staging",
        artifact="staging checklist",
        action="staging rollout",
        risk="test evidence",
        primary_slot="deployment_state",
        entities=("service_beta", "owner_bob", "cluster_south"),
        tags=("deploy", "staging", "beta", "release"),
        knowledge_scope=("deployment", "release", "staging", "validation"),
        query="service beta staging release evidence validation rollout",
    ),
    ScenarioSpec(
        code="api_gateway_patch",
        goal="Coordinate API gateway patch validation",
        asset="api gateway patch",
        owner="chris",
        domain="security",
        scope="prod",
        artifact="patch playbook",
        action="security patch",
        risk="waf regression",
        primary_slot="patch_state",
        entities=("api_gateway", "owner_chris", "waf_policy"),
        tags=("security", "patch", "gateway", "prod"),
        knowledge_scope=("security", "patch", "validation", "gateway"),
        query="api gateway patch waf regression validation security",
    ),
    ScenarioSpec(
        code="vendor_orion_procurement",
        goal="Track Orion sensor procurement approvals",
        asset="orion sensor order",
        owner="diana",
        domain="procurement",
        scope="plant_north",
        artifact="supplier packet",
        action="purchase release",
        risk="vendor certificate",
        primary_slot="procurement_state",
        entities=("vendor_orion", "plant_north", "sensor_cluster"),
        tags=("procurement", "vendor", "orion", "plant"),
        knowledge_scope=("procurement", "vendor", "certificate", "plant"),
        query="vendor orion procurement certificate plant north sensor order",
    ),
    ScenarioSpec(
        code="vendor_zephyr_invoice",
        goal="Resolve Zephyr invoice reconciliation",
        asset="zephyr invoice batch",
        owner="eric",
        domain="finance",
        scope="q2_close",
        artifact="invoice workbook",
        action="ledger close",
        risk="duplicate charge",
        primary_slot="invoice_state",
        entities=("vendor_zephyr", "ledger_q2", "finance_ops"),
        tags=("finance", "invoice", "zephyr", "reconcile"),
        knowledge_scope=("finance", "invoice", "reconciliation", "ledger"),
        query="zephyr invoice reconciliation ledger duplicate charge finance",
    ),
    ScenarioSpec(
        code="customer_titan_support",
        goal="Maintain Titan P1 support continuity",
        asset="titan p1 case",
        owner="fiona",
        domain="support",
        scope="region_east",
        artifact="support playbook",
        action="incident recovery",
        risk="sla breach",
        primary_slot="ticket_state",
        entities=("customer_titan", "sla_p1", "region_east"),
        tags=("support", "p1", "titan", "incident"),
        knowledge_scope=("support", "incident", "sla", "customer"),
        query="customer titan p1 escalation sla breach support workaround",
    ),
    ScenarioSpec(
        code="customer_nova_support",
        goal="Coordinate Nova escalation handling",
        asset="nova escalation case",
        owner="george",
        domain="support",
        scope="region_west",
        artifact="escalation guide",
        action="customer recovery",
        risk="handoff delay",
        primary_slot="ticket_state",
        entities=("customer_nova", "sla_p2", "region_west"),
        tags=("support", "nova", "escalation", "handoff"),
        knowledge_scope=("support", "customer", "escalation", "handoff"),
        query="customer nova escalation handoff recovery support west",
    ),
    ScenarioSpec(
        code="demand_forecast_analytics",
        goal="Validate south region demand forecast",
        asset="south demand model",
        owner="helen",
        domain="analytics",
        scope="q3",
        artifact="forecast notebook",
        action="forecast refresh",
        risk="feature drift",
        primary_slot="model_state",
        entities=("demand_forecast", "region_south", "quarter_q3"),
        tags=("analytics", "forecast", "demand", "q3"),
        knowledge_scope=("analytics", "forecast", "features", "modeling"),
        query="south region demand forecast feature drift analytics q3",
    ),
    ScenarioSpec(
        code="nutcracker_memory_research",
        goal="Evaluate Clark's nutcracker memory graph benchmark",
        asset="nutcracker memory benchmark",
        owner="ivy",
        domain="research",
        scope="chapter_4",
        artifact="benchmark sheet",
        action="chapter evaluation",
        risk="stale retrieval",
        primary_slot="memory_graph_state",
        entities=("clarks_nutcracker", "memory_graph", "chapter_4"),
        tags=("research", "memory_graph", "nutcracker", "benchmark"),
        knowledge_scope=("research", "long_term_memory", "graph", "benchmark"),
        query="clark nutcracker memory graph retrieval stale conflict benchmark",
    ),
    ScenarioSpec(
        code="elephant_context_runtime",
        goal="Review elephant-inspired context governance runtime",
        asset="context governance runtime",
        owner="julia",
        domain="runtime",
        scope="chapter_3",
        artifact="context policy",
        action="budgeted orchestration",
        risk="context overflow",
        primary_slot="context_runtime_state",
        entities=("elephant_mgcm", "context_budget", "chapter_3"),
        tags=("runtime", "context", "elephant", "mgcm"),
        knowledge_scope=("runtime", "context", "budget", "orchestration"),
        query="elephant mgcm context budget planner reviewer compression runtime",
    ),
    ScenarioSpec(
        code="compliance_audit_eu",
        goal="Prepare EU retention compliance audit",
        asset="eu retention audit",
        owner="karen",
        domain="compliance",
        scope="eu_market",
        artifact="audit checklist",
        action="audit signoff",
        risk="retention gap",
        primary_slot="audit_state",
        entities=("gdpr_audit", "market_eu", "retention_policy"),
        tags=("compliance", "audit", "eu", "retention"),
        knowledge_scope=("compliance", "audit", "retention", "policy"),
        query="eu retention audit evidence policy conflict compliance",
    ),
    ScenarioSpec(
        code="warehouse_robot_ops",
        goal="Stabilize gamma warehouse robot fleet",
        asset="gamma robot fleet",
        owner="leo",
        domain="operations",
        scope="night_shift",
        artifact="robot ops guide",
        action="warehouse recovery",
        risk="battery drift",
        primary_slot="warehouse_state",
        entities=("warehouse_gamma", "robot_fleet", "night_shift"),
        tags=("operations", "warehouse", "robot", "gamma"),
        knowledge_scope=("operations", "warehouse", "robotics", "recovery"),
        query="warehouse gamma robot fleet battery drift operations recovery",
    ),
)

ROLE_CYCLE: tuple[str, ...] = ("planner", "reviewer", "operator", "auditor", "manager", "analyst")
DEFAULT_BROWSER_URL = "http://127.0.0.1:7574/browser/"


class HashedDemoEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimensions: int = 3, *, salt: str | int = 0) -> None:
        self.dimensions = dimensions
        self.salt = str(salt)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> list[float]:
        tokens = re.findall(r"[a-z0-9_']+", text.lower())
        vector = [0.0] * self.dimensions
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(f"{self.salt}:{token}".encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % self.dimensions
            weight = 1.0 + (len(token) / 12.0)
            vector[index] += weight
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [round(value / norm, 6) for value in vector]


def _scenario_variant_name(prefix: str, spec: ScenarioSpec, *, replica_index: int) -> str:
    if replica_index == 0:
        return f"{prefix}{spec.code}"
    return f"{prefix}{spec.code}__cohort_{replica_index + 1:02d}"


def _cohort_tag(replica_index: int) -> str:
    return f"cohort_{replica_index + 1:02d}"


def build_demo_request(
    prefix: str,
    spec: ScenarioSpec,
    *,
    replica_index: int = 0,
    scale_multiplier: int = 1,
) -> RecallRequest:
    task_family = _scenario_variant_name(prefix, spec, replica_index=replica_index)
    knowledge_scope = list(spec.knowledge_scope)
    tags = list(spec.tags)
    entities = list(spec.entities[:2])
    if scale_multiplier > 1:
        cohort = _cohort_tag(replica_index)
        knowledge_scope.append(cohort)
        tags.append(cohort)
        entities.append(cohort)
    return RecallRequest(
        query=spec.query,
        knowledge_scope=knowledge_scope,
        tags=tags,
        entities=entities,
        task_family=task_family,
    )


def _event_value(stage: int) -> tuple[str, str]:
    values = (
        ("planned", "positive"),
        ("preparing", "positive"),
        ("blocked", "negative"),
        ("reviewing", "positive"),
        ("pending", "positive"),
        ("approved", "positive"),
        ("executing", "positive"),
        ("validated", "positive"),
        ("stable", "positive"),
        ("stable", "positive"),
    )
    return values[stage]


def _event_summary(spec: ScenarioSpec, round_idx: int, stage: int, bundle_id: str) -> tuple[str, str]:
    if stage == 0:
        return (
            f"Baseline rule for {spec.asset}: {spec.owner} must review the {spec.artifact} before {spec.action}.",
            f"Initial planning note captured for {spec.goal}.",
        )
    if stage == 1:
        return (
            f"Evidence bundle {bundle_id} collected for {spec.asset}; checklist synced with {spec.owner}.",
            f"Evidence package prepared for {spec.action}.",
        )
    if stage == 2:
        return (
            f"Contradictory field note says {spec.asset} is blocked because {spec.risk} is unresolved.",
            f"Blocking signal recorded for {spec.asset}.",
        )
    if stage == 3:
        return (
            f"Follow-up review reclassifies {spec.asset} as reviewing after new evidence arrived.",
            f"Review state updated for {spec.goal}.",
        )
    if stage == 4:
        return (
            f"Approval request submitted for {spec.asset} with {bundle_id} attached to the {spec.artifact}.",
            f"Approval queue updated for {spec.action}.",
        )
    if stage == 5:
        return (
            f"Approval granted by {spec.owner}; {spec.asset} is approved for {spec.action}.",
            f"Approved state confirmed for {spec.goal}.",
        )
    if stage == 6:
        return (
            f"Execution started for {spec.asset}; operator followed the {spec.artifact}.",
            f"Execution state opened for {spec.asset}.",
        )
    if stage == 7:
        return (
            f"Validation report confirms {spec.asset} passed checks in {spec.scope}.",
            f"Validation completed for {spec.action}.",
        )
    if stage == 8:
        return (
            f"Latest operational note marks {spec.asset} stable and recommends reuse.",
            f"Stable operating note stored for {spec.goal}.",
        )
    return (
        f"Lesson learned capsule records fallback, evidence links, and next-step guidance for {spec.asset}.",
        f"Lesson capsule captured for round {round_idx + 1} of {spec.goal}.",
    )


def _status_for_round(round_idx: int, stage: int) -> str:
    if round_idx == 0:
        return "deprecated" if stage in (2, 3) else "candidate"
    if round_idx == 1:
        return "active"
    return "validated"


def _confidence_for_round(round_idx: int, stage: int) -> float:
    if round_idx == 0:
        return round(0.42 + 0.015 * stage, 3)
    if round_idx == 1:
        return round(0.72 + 0.008 * stage, 3)
    return round(min(0.98, 0.88 + 0.01 * stage), 3)


def build_demo_candidates(prefix: str, *, scale_multiplier: int = 1) -> list[MemoryCapsuleCandidate]:
    if scale_multiplier <= 0:
        raise ValueError("scale_multiplier must be positive.")
    now = now_utc()
    candidates: list[MemoryCapsuleCandidate] = []
    for scenario_index, spec in enumerate(SCENARIOS):
        for replica_index in range(scale_multiplier):
            base_times = (
                now - timedelta(days=190 - scenario_index),
                now - timedelta(days=45 - scenario_index),
                now - timedelta(days=4 + (scenario_index % 3)),
            )
            scenario_prefix = _scenario_variant_name(prefix, spec, replica_index=replica_index)
            task_id = f"{scenario_prefix}:task"
            thread_family = f"{scenario_prefix}-thread"
            cohort = _cohort_tag(replica_index)
            for round_idx, base_time in enumerate(base_times):
                for stage in range(10):
                    ordinal = round_idx * 10 + stage + 1
                    capsule_id = f"{scenario_prefix}-caps-{ordinal:03d}"
                    role = ROLE_CYCLE[(scenario_index + stage + replica_index) % len(ROLE_CYCLE)]
                    thread_id = f"{thread_family}:{role}"
                    bundle_id = f"{spec.code}-c{replica_index + 1:02d}-bundle-r{round_idx + 1}-s{stage + 1}"
                    summary, outcome = _event_summary(spec, round_idx, stage, bundle_id)
                    if scale_multiplier > 1:
                        summary = f"{summary} {cohort}."
                        outcome = f"{outcome} {cohort}."
                    primary_value, polarity = _event_value(stage)
                    evidence_refs = [bundle_id]
                    if stage > 0:
                        evidence_refs.append(f"{spec.code}-c{replica_index + 1:02d}-trail-r{round_idx + 1}-s{stage}")
                    source_memory_refs: list[str] = []
                    if stage > 0:
                        source_memory_refs.append(f"{scenario_prefix}-caps-{ordinal - 1:03d}")
                    if stage > 1:
                        source_memory_refs.append(f"{scenario_prefix}-caps-{ordinal - 2:03d}")
                    claims = [
                        {
                            "slot": spec.primary_slot,
                            "value": primary_value,
                            "polarity": polarity,
                            "scope": spec.scope,
                            "evidence_ids": evidence_refs,
                        },
                        {
                            "slot": "owner",
                            "value": spec.owner,
                            "polarity": "positive",
                            "scope": spec.scope,
                            "evidence_ids": evidence_refs[:1],
                        },
                    ]
                    if stage in (2, 4, 7, 9):
                        claims.append(
                            {
                                "slot": "risk_focus",
                                "value": spec.risk.replace(" ", "_"),
                                "polarity": "negative" if stage == 2 else "positive",
                                "scope": spec.scope,
                                "evidence_ids": evidence_refs,
                            }
                        )
                    knowledge_scope = [*spec.knowledge_scope, spec.scope, f"round_{round_idx + 1}"]
                    tags = [*spec.tags, f"round_{round_idx + 1}", f"stage_{stage + 1}"]
                    entities = [*spec.entities, spec.owner, spec.scope]
                    if scale_multiplier > 1:
                        knowledge_scope.append(cohort)
                        tags.append(cohort)
                        entities.append(cohort)
                    candidates.append(
                        MemoryCapsuleCandidate(
                            capsule_id=capsule_id,
                            agent_id=role,
                            run_id=f"{scenario_prefix}-run-r{round_idx + 1}",
                            thread_id=thread_id,
                            thread_family=thread_family,
                            task_id=task_id,
                            task_family=task_id.split(":", 1)[0],
                            created_at=base_time + timedelta(minutes=stage * 7 + round_idx),
                            goal=spec.goal,
                            summary=summary,
                            outcome=outcome,
                            knowledge_scope=knowledge_scope,
                            tags=tags,
                            entities=entities,
                            claims=claims,
                            evidence_refs=evidence_refs,
                            source_memory_refs=source_memory_refs,
                            salience_score=round(0.68 + 0.01 * stage + 0.03 * round_idx, 3),
                            confidence=_confidence_for_round(round_idx, stage),
                            status=_status_for_round(round_idx, stage),
                        )
                    )
    return candidates


__all__ = [
    "DEFAULT_BROWSER_URL",
    "HashedDemoEmbeddingProvider",
    "SCENARIOS",
    "ScenarioSpec",
    "build_demo_candidates",
    "build_demo_request",
]
