METHOD_MAPPING = {
    "Elephant Attention": {
        "context_strategy": {
            "budget_aware_compaction": True,
            "salience_mode": "rule",
        },
        "memory_governance_weights": {
            "relevance_weight": 4.0,
            "evidence_weight": 1.8,
            "reuse_weight": 0.8,
            "outcome_weight": 1.2,
            "recency_weight": 0.0,
        },
    },
    "North American Seagull Memory": {
        "memory_governance_kind": "hybrid_long_memory",
        "allow_cross_thread_recall": True,
        "recall_top_k": 6,
    },
    "Long-Horizon Attention": {
        "history_retention_policy": "window_plus_summary",
        "overflow_strategy": "compress",
    },
    "Context Compression": {
        "budget_aware_compaction": True,
        "typed_segments": True,
    },
    "event-centric observability": {
        "sqlite": True,
        "todo_projection": True,
    },
}
