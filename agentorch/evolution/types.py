from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Genome(BaseModel):
    id: str
    generation: int = 0
    parent_ids: list[str] = Field(default_factory=list)
    genes: dict[str, Any] = Field(default_factory=dict)
    fitness: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    genome_id: str
    fitness: float
    metrics: dict[str, float] = Field(default_factory=dict)
    task_results: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GenerationResult(BaseModel):
    generation: int
    population: list[Genome] = Field(default_factory=list)
    evaluations: list[EvaluationResult] = Field(default_factory=list)
    best_genome_id: str | None = None
    best_fitness: float | None = None


class EvolutionConfig(BaseModel):
    algorithm_kind: str = "genetic"
    algorithm_config: dict[str, Any] = Field(default_factory=dict)
    population_size: int = 8
    generations: int = 5
    selection_strategy: str = "top_k"
    mutation_rate: float = 0.2
    elitism: int = 1
    selection_size: int | None = None
    seed: int = 7
    evaluation_budget: int | None = None
    early_stop_patience: int | None = None
    parallel_evaluations: int = 1
    objective_weights: dict[str, float] = Field(default_factory=dict)
    retain_history: bool = True
    search_targets: list[str] = Field(
        default_factory=lambda: [
            "reasoning.kind",
            "reasoning.config",
            "rag.mode",
            "rag.mount",
            "rag.injection_policy",
            "rag.classic.top_k",
            "rag.deliberative.max_steps",
            "tools.policy",
            "delegation.policy",
            "memory.governance",
            "workflow.template",
        ]
    )


class EvolutionResult(BaseModel):
    best_genome: Genome
    best_evaluation: EvaluationResult
    history: list[GenerationResult] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
