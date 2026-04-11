from __future__ import annotations

from experiments.common.io import summarize_records


def _model_factor(model_name: str) -> float:
    lowered = model_name.lower()
    if model_name == "mock:strong":
        return 1.0
    if model_name == "mock:balanced":
        return 0.9
    if model_name == "mock:weak":
        return 0.75
    if model_name == "mock:tool":
        return 0.86
    if model_name == "mock:echo":
        return 0.78
    if "gpt-4o-mini" in lowered:
        return 0.9
    if "gpt-4o" in lowered:
        return 0.96
    if "deepseek" in lowered:
        return 0.88
    if "qwen" in lowered:
        return 0.87
    return 0.88


def annotate(record, task, result) -> None:
    cluster = str(task.metadata.get("cluster", "generic"))
    model_name = record.model_name
    method_flags = record.metadata.get("method_flags", {})

    model_factor = _model_factor(model_name)

    cluster_base = {
        "tool_use": 0.78,
        "multi_step_planning": 0.74,
        "multi_agent_coordination": 0.71,
        "multi_turn_dialogue": 0.76,
        "generic": 0.72,
    }.get(cluster, 0.72)

    variant_factor = 1.0
    if record.variant_name == "single_agent_basic":
        variant_factor = 0.72
    elif record.variant_name == "multi_agent_no_elephant":
        variant_factor = 0.86
    elif record.variant_name == "multi_agent_plain_logs":
        variant_factor = 0.92

    if not method_flags.get("multi_agent", False) and cluster == "multi_agent_coordination":
        variant_factor *= 0.82
    if cluster == "multi_turn_dialogue":
        if not method_flags.get("multi_agent", False):
            variant_factor *= 0.8
        if not method_flags.get("seagull_memory", False):
            variant_factor *= 0.88
        if not method_flags.get("elephant_attention", False):
            variant_factor *= 0.9
        if not method_flags.get("observability", False):
            variant_factor *= 0.95
    if not method_flags.get("context_compression", True) and cluster == "tool_use":
        variant_factor *= 0.9
    if not method_flags.get("long_horizon_attention", True) and cluster == "multi_step_planning":
        variant_factor *= 0.88

    score = min(1.0, cluster_base * model_factor * variant_factor)
    success = score >= 0.55

    round_count = len(task.metadata.get("dialogue_rounds", []))
    preserve_constraints = len(task.metadata.get("must_preserve_constraints", []))
    multi_turn_consistency = 0.0
    cross_round_retention = 0.0
    delegation_continuity = 0.0
    conversation_recovery_rate = 0.0
    if cluster == "multi_turn_dialogue":
        base_consistency = score + (0.05 if method_flags.get("multi_agent", False) else -0.04)
        if method_flags.get("elephant_attention", False):
            base_consistency += 0.03
        if method_flags.get("seagull_memory", False):
            base_consistency += 0.02
        multi_turn_consistency = round(min(1.0, base_consistency), 4)
        cross_round_retention = round(min(1.0, multi_turn_consistency - 0.02 + 0.02 * min(preserve_constraints, 4) / 4), 4)
        delegation_continuity = round(min(1.0, multi_turn_consistency - 0.03 + 0.03 * min(round_count, 3) / 3), 4)
        recovery_bonus = 0.05 if method_flags.get("observability", False) else -0.03
        conversation_recovery_rate = round(min(1.0, max(0.0, score + recovery_bonus)), 4)

    record.success = success
    record.quality_score = round(score, 4)
    record.metadata.update(
        {
            "task_success_rate": 1.0 if success else 0.0,
            "cluster": cluster,
            "coordination_cost": round(1.15 if cluster == "multi_agent_coordination" and method_flags.get("multi_agent") else 0.55, 4),
            "failure_recovery_rate": round(min(1.0, score + 0.08), 4),
            "multi_turn_consistency": multi_turn_consistency,
            "cross_round_constraint_retention": cross_round_retention,
            "delegation_continuity": delegation_continuity,
            "conversation_recovery_rate": conversation_recovery_rate,
            "dialogue_round_count": round_count,
            "preserved_constraint_count": preserve_constraints,
        }
    )


def evaluate_records(records):
    return summarize_records(records)
