from __future__ import annotations

from collections import OrderedDict

from .models import (
    ElephantChapterConfig,
    ElephantVariantSpec,
    default_stage_attention_profiles,
    flatten_stage_attention_profiles,
)


def _build_variants() -> OrderedDict[str, ElephantVariantSpec]:
    default_scope = ["planning"]
    elephant_full = ElephantVariantSpec(
        name="elephant_full",
        description="Full elephant chapter mechanism with hybrid salience, stage attention, redundancy suppression, budgeted compaction, and guided routing.",
        category="baseline",
        aliases=["full_framework"],
        multi_agent=True,
        use_elephant_selector=True,
        use_elephant_route_planner=True,
        use_elephant_memory_evaluator=True,
        chapter_config=ElephantChapterConfig(
            selection_mode="hybrid",
            overflow_action="compress",
            stage_attention_profiles=default_stage_attention_profiles(),
            use_builtin_stage_profiles=False,
            redundancy_inhibition_enabled=True,
            route_mode="guided",
            default_knowledge_scope=default_scope,
        ),
        default_knowledge_scope=default_scope,
    )
    variants = OrderedDict(
        [
            (
                elephant_full.name,
                elephant_full,
            ),
            (
                "multi_agent_default_context",
                ElephantVariantSpec(
                    name="multi_agent_default_context",
                    description="Default AgentTorch multi-agent context governance without elephant-specific selector, planner, or evaluator customization.",
                    category="baseline",
                    aliases=["multi_agent_no_elephant"],
                    multi_agent=True,
                    use_elephant_selector=False,
                    use_elephant_route_planner=False,
                    use_elephant_memory_evaluator=False,
                    chapter_config=ElephantChapterConfig(
                        selection_mode="rule",
                        overflow_action="compress",
                        stage_attention_profiles={},
                        use_builtin_stage_profiles=True,
                        redundancy_inhibition_enabled=True,
                        route_mode="guided",
                        default_knowledge_scope=default_scope,
                    ),
                    default_knowledge_scope=default_scope,
                ),
            ),
            (
                "single_agent_long_context",
                ElephantVariantSpec(
                    name="single_agent_long_context",
                    description="Single-agent long-context baseline without multi-agent delegation or matriarch routing.",
                    category="baseline",
                    aliases=[],
                    multi_agent=False,
                    use_elephant_selector=False,
                    use_elephant_route_planner=False,
                    use_elephant_memory_evaluator=False,
                    chapter_config=ElephantChapterConfig(
                        char_budget=22000,
                        conversation_window=10,
                        selection_mode="rule",
                        overflow_action="compress",
                        stage_attention_profiles={},
                        use_builtin_stage_profiles=True,
                        redundancy_inhibition_enabled=True,
                        route_mode="guided",
                        retrieval_evidence_max_items=6,
                        retrieval_citation_max_items=8,
                        shared_memory_max_items=6,
                        default_knowledge_scope=default_scope,
                    ),
                    default_knowledge_scope=default_scope,
                ),
            ),
            (
                "elephant_rule_only",
                ElephantVariantSpec(
                    name="elephant_rule_only",
                    description="Keep elephant structure but fall back from hybrid to rule-only salience.",
                    category="ablation",
                    chapter_config=elephant_full.chapter_config.merged(selection_mode="rule"),
                    default_knowledge_scope=default_scope,
                ),
            ),
            (
                "elephant_flat_attention",
                ElephantVariantSpec(
                    name="elephant_flat_attention",
                    description="Keep elephant governance but remove stage-specific profiles and use one flat default profile.",
                    category="ablation",
                    chapter_config=elephant_full.chapter_config.merged(
                        stage_attention_profiles=flatten_stage_attention_profiles(),
                        use_builtin_stage_profiles=False,
                    ),
                    default_knowledge_scope=default_scope,
                ),
            ),
            (
                "elephant_no_redundancy",
                ElephantVariantSpec(
                    name="elephant_no_redundancy",
                    description="Disable lateral inhibition redundancy suppression while keeping salience ranking.",
                    category="ablation",
                    chapter_config=elephant_full.chapter_config.merged(redundancy_inhibition_enabled=False),
                    default_knowledge_scope=default_scope,
                ),
            ),
            (
                "elephant_drop_only",
                ElephantVariantSpec(
                    name="elephant_drop_only",
                    description="When over budget, only drop low-priority context and do not switch to compacted representations.",
                    category="ablation",
                    chapter_config=elephant_full.chapter_config.merged(overflow_action="drop_low_priority"),
                    default_knowledge_scope=default_scope,
                ),
            ),
            (
                "elephant_distributed_routing",
                ElephantVariantSpec(
                    name="elephant_distributed_routing",
                    description="Keep context governance but switch matriarch guided routing to distributed routing.",
                    category="ablation",
                    chapter_config=elephant_full.chapter_config.merged(route_mode="distributed"),
                    default_knowledge_scope=default_scope,
                ),
            ),
        ]
    )
    return variants


_VARIANTS = _build_variants()
_ALIASES = {
    alias: name
    for name, spec in _VARIANTS.items()
    for alias in spec.aliases
}


def get_elephant_variant(name: str) -> ElephantVariantSpec:
    resolved_name = _ALIASES.get(name, name)
    try:
        return _VARIANTS[resolved_name].model_copy(deep=True)
    except KeyError as exc:  # pragma: no cover - defensive guard
        available = ", ".join(list(_VARIANTS.keys()) + list(_ALIASES.keys()))
        raise KeyError(f"Unknown elephant variant '{name}'. Available variants: {available}") from exc


def list_elephant_variants() -> list[ElephantVariantSpec]:
    return [spec.model_copy(deep=True) for spec in _VARIANTS.values()]


__all__ = ["get_elephant_variant", "list_elephant_variants"]
