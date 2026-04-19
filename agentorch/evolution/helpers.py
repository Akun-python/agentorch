from __future__ import annotations

from typing import Any

from agentorch.config import RuntimeConfig
from agentorch.knowledge import RagStrategyConfig
from agentorch.reasoning import ReasoningStrategyConfig
from agentorch.workflow import Workflow

from .templates import resolve_evolution_workflow_template
from .types import Genome


def reasoning_strategy_from_genome(genome: Genome) -> ReasoningStrategyConfig:
    reasoning = dict(genome.genes.get("reasoning", {}))
    kind = reasoning.get("kind", "react")
    config = dict(reasoning.get("config", {}))
    return ReasoningStrategyConfig(
        kind=kind,
        config=config,
        allow_tool_calls=reasoning.get("allow_tool_calls", True),
        allow_retrieval=reasoning.get("allow_retrieval", True),
        allow_delegation=reasoning.get("allow_delegation", False),
    )


def rag_strategy_from_genome(genome: Genome) -> RagStrategyConfig:
    rag = dict(genome.genes.get("rag", {}))
    return RagStrategyConfig(
        mode=rag.get("mode", "deliberative"),
        mount=rag.get("mount", "inline"),
        injection_policy=rag.get("injection_policy", "full_report"),
        knowledge_scope=list(rag.get("knowledge_scope", [])),
        source_types=list(rag.get("source_types", [])),
        file_types=list(rag.get("file_types", [])),
        top_k=rag.get("top_k", rag.get("config", {}).get("top_k", 5)),
        must_cover=list(rag.get("must_cover", [])),
        max_steps=rag.get("max_steps", rag.get("config", {}).get("max_steps", 3)),
        rerank_enabled=rag.get("rerank_enabled", False),
        fallback_mode=rag.get("fallback_mode", "off"),
        classic=rag.get("classic", {}),
        deliberative=rag.get("deliberative", {}),
        hybrid=rag.get("hybrid", {}),
    )


def runtime_config_from_genome(genome: Genome, *, base: RuntimeConfig | None = None) -> RuntimeConfig:
    config = base.model_copy(deep=True) if base is not None else RuntimeConfig()
    config.reasoning_strategy = reasoning_strategy_from_genome(genome)
    config.rag_strategy = rag_strategy_from_genome(genome)
    config.enable_retrieval = config.rag_strategy.mode != "off"
    return config


def workflow_from_genome(
    genome: Genome,
    *,
    base: Workflow | None = None,
    templates: dict[str, Workflow | Any] | None = None,
) -> Workflow | None:
    workflow = dict(genome.genes.get("workflow", {}))
    template = workflow.pop("template", None)
    if template is None:
        return base.model_copy(deep=True) if base is not None else None
    return resolve_evolution_workflow_template(template, templates=templates, **workflow)


def candidate_from_genome(genome: Genome) -> dict[str, Any]:
    return {
        "genes": genome.genes,
        "reasoning_strategy": reasoning_strategy_from_genome(genome).model_dump(),
        "rag_strategy": rag_strategy_from_genome(genome).model_dump(),
        "workflow_template": genome.genes.get("workflow", {}).get("template"),
    }
