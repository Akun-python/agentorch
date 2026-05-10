from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentorch.knowledge.base import EmbeddingProvider


class GraphMemoryConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Connection and schema.
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "neo4j"
    neo4j_database: str = "neo4j"
    auto_create_schema: bool = True
    vector_index_name: str = "memory_capsule_embedding_idx"
    fulltext_index_name: str = "memory_capsule_fulltext_idx"

    # Embeddings.
    embedding_provider: EmbeddingProvider | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Promotion scoring.
    promotion_threshold: float = 0.6
    promotion_val_weight: float = 0.3
    promotion_reuse_weight: float = 0.2
    promotion_out_weight: float = 0.2
    promotion_gen_weight: float = 0.2
    promotion_noise_weight: float = 0.1
    promotion_min_evidence_refs: int = 1
    promotion_result_keywords: tuple[str, ...] = (
        "should",
        "must",
        "use",
        "deploy",
        "rollback",
        "retry",
        "migrate",
        "mitigation",
        "policy",
        "plan",
    )

    # Retrieval sizing.
    neighborhood_limit: int = 64
    top_candidates: int = 6
    top_seeds: int = 3
    expansion_hops: int = 1
    max_nodes: int = 12
    max_edges: int = 24

    # Scoring and suppression.
    scope_overlap_threshold: float = 0.4
    reuse_weight: float = 0.15
    confidence_weight: float = 0.5
    scene_match_weight: float = 0.9
    stale_penalty_weight: float = 1.0
    conflict_penalty_weight: float = 0.35
    stale_after_days: int = 120
    stale_low_confidence_threshold: float = 0.65
    enable_stale_filter: bool = True
    enable_conflict_filter: bool = True

    # Status and relation policy.
    relation_types: tuple[str, ...] = (
        "TEMPORAL_NEXT",
        "SAME_TASK",
        "EVIDENCE_SUPPORTS",
        "SCOPE_OVERLAP",
        "REVISES",
        "CONFLICTS_WITH",
    )
    blocked_statuses: tuple[str, ...] = ("deprecated",)
    status_priority: dict[str, int] = Field(
        default_factory=lambda: {
            "validated": 3,
            "active": 3,
            "candidate": 2,
            "deprecated": 0,
        }
    )

    @model_validator(mode="after")
    def _validate_ranges(self) -> "GraphMemoryConfig":
        if self.embedding_dimensions <= 0:
            raise ValueError("embedding_dimensions must be > 0")
        if self.top_candidates <= 0:
            raise ValueError("top_candidates must be > 0")
        if self.top_seeds <= 0:
            raise ValueError("top_seeds must be > 0")
        if self.top_candidates < self.top_seeds:
            raise ValueError("top_candidates must be >= top_seeds")
        if self.max_nodes <= 0:
            raise ValueError("max_nodes must be > 0")
        if self.max_edges <= 0:
            raise ValueError("max_edges must be > 0")
        if self.neighborhood_limit <= 0:
            raise ValueError("neighborhood_limit must be > 0")
        if self.expansion_hops <= 0:
            raise ValueError("expansion_hops must be > 0")
        if not 0.0 <= self.scope_overlap_threshold <= 1.0:
            raise ValueError("scope_overlap_threshold must be between 0 and 1")
        if self.stale_after_days <= 0:
            raise ValueError("stale_after_days must be > 0")
        if not 0.0 <= self.promotion_threshold <= 2.0:
            raise ValueError("promotion_threshold must be between 0 and 2")
        return self
