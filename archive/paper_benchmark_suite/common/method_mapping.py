METHOD_MAPPING = {
    "Elephant Attention": {
        "context_policy": {
            "overflow_action": "compress",
            "selection_mode": "rule",
        },
        "memory_policy_weights": {
            "relevance_weight": 4.0,
            "evidence_weight": 1.8,
            "reuse_weight": 0.8,
            "outcome_weight": 1.2,
            "recency_weight": 0.0,
        },
    },
    "North American Seagull Memory": {
        "memory_policy_mode": "hybrid",
        "allow_cross_thread_recall": True,
        "recall_top_k": 6,
    },
    "Long-Horizon Attention": {
        "retention_mode": "window_plus_summary",
        "overflow_action": "compress",
    },
    "Context Compression": {
        "overflow_action": "compress",
        "typed_segments": True,
    },
    "event-centric observability": {
        "sqlite": True,
        "todo_projection": True,
    },
}
