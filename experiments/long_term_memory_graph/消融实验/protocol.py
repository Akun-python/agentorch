from __future__ import annotations

from typing import Any

from ..core import ABLATION_VARIANTS


# 消融协议只描述实验设计，不执行任何模型调用。
ABLATION_PROTOCOL: dict[str, Any] = {
    "name": "clarks_nutcracker_ablation_protocol",
    "reference": "Clark's Nutcracker long-term memory graph ablation design",
    "design_scope": "固定变体消融 + 参数扫描，共用 E1 case 集与 token budget。",
}


ABLATION_VARIANT_DESCRIPTIONS: dict[str, str] = {
    "full": "完整图谱机制，包含场景匹配、时间边、修正边、冲突抑制与陈旧抑制。",
    "wo_scene_match": "关闭场景匹配权重，仅依赖语义/规则召回。",
    "wo_temporal_edges": "关闭 TEMPORAL_NEXT 等时间边扩展。",
    "wo_revision_edges": "关闭 REVISES 修正边扩展。",
    "wo_conflict_suppression": "保留冲突边，但不压制冲突失败节点。",
    "wo_stale_suppression": "保留旧节点，不执行陈旧抑制。",
    "graph_no_policy": "保留图结构，但关闭治理策略约束。",
    "multi_level_topk": "放宽多级 top-k，观察召回深度变化。",
    "scene_weight_0_3": "将场景匹配权重降为 0.3。",
    "scene_weight_1_2": "将场景匹配权重升为 1.2。",
    "topk_small": "使用更小的 top-k 配置。",
    "topk_large": "使用更大的 top-k 配置。",
}


SWEEP_PARAMETER_DESCRIPTIONS: dict[str, str] = {
    "top_candidates": "候选召回上限。",
    "top_seeds": "扩展种子上限。",
    "max_nodes": "最终返回节点上限。",
    "max_edges": "最终返回边上限。",
    "scene_match_weight": "场景匹配权重。",
    "stale_penalty_weight": "陈旧惩罚权重。",
    "conflict_penalty_weight": "冲突惩罚权重。",
}


def build_ablation_protocol_metadata(
    variants: tuple[str, ...],
    sweep_parameters: dict[str, list[float | int]] | None,
) -> dict[str, Any]:
    """把固定消融变体和参数扫描配置写入 manifest。"""

    return {
        **ABLATION_PROTOCOL,
        "all_variants": list(ABLATION_VARIANTS),
        "selected_variants": list(variants),
        "variant_descriptions": {
            variant: ABLATION_VARIANT_DESCRIPTIONS.get(variant, "")
            for variant in ABLATION_VARIANTS
        },
        "sweep_parameters": dict(sweep_parameters or {}),
        "sweep_parameter_descriptions": dict(SWEEP_PARAMETER_DESCRIPTIONS),
    }
