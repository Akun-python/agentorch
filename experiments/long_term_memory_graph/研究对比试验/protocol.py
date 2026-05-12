from __future__ import annotations

from typing import Any

from ..core import (
    BASELINE_METHODS,
    CORE_LOCAL_BASELINE_METHODS,
    LITERATURE_ONLY_METHODS,
    NON_OFFICIAL_PROXY_EXTENSION_METHODS,
    OFFICIAL_BASELINE_METHODS,
    PROXY_EXTENSION_METHODS,
)


HYPERMEM_REFERENCE_PROTOCOL: dict[str, Any] = {
    "name": "hypermem_style_long_term_memory_comparison",
    "reference": "参考文献/长期记忆对比参考文献.pdf",
    "benchmark_shape": {
        "question_types": ["Single-hop", "Multi-hop", "Temporal", "Open Domain", "Overall"],
        "judge_metric": "LLM-as-a-judge accuracy",
        "judge_model_in_reference": "GPT-4o-mini",
        "independent_runs": 3,
    },
    "token_efficiency": {
        "relative_token_baseline": "mem0_memory",
        "reported_fields": ["avg_input_tokens", "avg_relative_tokens", "token_efficiency_score"],
    },
    "implementation_boundary": (
        "本实验用 AgentTorch 统一承载答案生成、线程追踪、token 统计和产物落盘；"
        "当前已接入的官方 adapter 为 mem0、LangMem、Zep；其余方法仍以受控 proxy adapter 表示，正式投稿结果必须替换为官方实现或明确标注。"
    ),
}


BASELINE_GROUPS: dict[str, list[str]] = {
    "rag_methods": [
        "rag_chunk_memory",
        "graph_rag_memory",
        "light_rag_memory",
        "hippo_rag2_memory",
        "hypergraph_rag_memory",
    ],
    "memory_systems": [
        "openai_memory",
        "langmem_memory",
        "zep_memory",
        "amem_memory",
        "mem0_memory",
        "mem0_graph_memory",
        "mirix_memory",
        "memobase_memory",
        "memu_memory",
        "memos_memory",
    ],
    "ours": ["clarks_nutcracker_graph"],
}


METHOD_DESCRIPTIONS: dict[str, str] = {
    "rag_chunk_memory": "Chunk-based RAG proxy; no explicit long-term memory graph.",
    "graph_rag_memory": "GraphRAG proxy; pairwise graph expansion without revision/conflict/stale governance.",
    "light_rag_memory": "LightRAG proxy; hybrid lexical-semantic retrieval with lightweight graph expansion.",
    "hippo_rag2_memory": "HippoRAG 2 proxy; episodic/temporal path-oriented graph retrieval.",
    "hypergraph_rag_memory": "HyperGraphRAG proxy; task/topic cluster retrieval as a hyperedge-like control.",
    "openai_memory": "OpenAI memory proxy; recent high-confidence persistent memories.",
    "langmem_memory": "LangMem baseline; official adapter available when configured, otherwise fallback proxy.",
    "zep_memory": "Zep baseline; official adapter available when configured, otherwise fallback proxy.",
    "amem_memory": "A-Mem proxy; adaptive salient memory selection.",
    "mem0_memory": "Mem0 baseline; official adapter available when configured, otherwise fallback proxy.",
    "mem0_graph_memory": "Mem0g proxy; Mem0-style graph expansion.",
    "mirix_memory": "MIRIX proxy; episodic state plus graph relation retrieval.",
    "memobase_memory": "Memobase proxy; profile and event memory retrieval.",
    "memu_memory": "MemU proxy; compact personalized memory retrieval.",
    "memos_memory": "MemOS proxy; hierarchical memory scheduling proxy.",
    "clarks_nutcracker_graph": "Full Clark's nutcracker inspired memory capsule graph.",
}

REFERENCE_CATALOG: dict[str, dict[str, str]] = {
    "001": {
        "title": "Evaluating Very Long-Term Conversational Memory of LLM Agents",
        "kind": "paper_pdf",
        "local_file": "参考文献/长期记忆基线对比参考文献/001_locomo_maharana_acl2024.pdf",
        "url": "https://aclanthology.org/2024.acl-long.747/",
    },
    "002": {
        "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        "kind": "paper_pdf",
        "local_file": "参考文献/长期记忆基线对比参考文献/002_rag_lewis2020.pdf",
        "url": "https://arxiv.org/abs/2005.11401",
    },
    "003": {
        "title": "From Local to Global: A Graph RAG Approach to Query-Focused Summarization",
        "kind": "paper_pdf",
        "local_file": "参考文献/长期记忆基线对比参考文献/003_graphrag_edge2024.pdf",
        "url": "https://arxiv.org/abs/2404.16130",
    },
    "004": {
        "title": "LightRAG: Simple and Fast Retrieval-Augmented Generation",
        "kind": "paper_pdf",
        "local_file": "参考文献/长期记忆基线对比参考文献/004_lightrag_guo2025.pdf",
        "url": "https://aclanthology.org/2025.findings-emnlp.568/",
    },
    "005": {
        "title": "From RAG to Memory: Non-Parametric Continual Learning for Large Language Models",
        "kind": "paper_pdf",
        "local_file": "参考文献/长期记忆基线对比参考文献/005_hipporag2_gutierrez2025.pdf",
        "url": "https://arxiv.org/abs/2502.14802",
    },
    "006": {
        "title": "HyperGraphRAG: Retrieval-Augmented Generation with Hypergraph-Structured Knowledge Representation",
        "kind": "paper_pdf",
        "local_file": "参考文献/长期记忆基线对比参考文献/006_hypergraphrag_luo2025.pdf",
        "url": "https://arxiv.org/abs/2503.21322",
    },
    "007": {
        "title": "Memory and new controls for ChatGPT",
        "kind": "official_url_note",
        "local_file": "参考文献/长期记忆基线对比参考文献/007_openai_memory_reference.md",
        "url": "https://openai.com/index/memory-and-new-controls-for-chatgpt/",
    },
    "008": {
        "title": "LangMem: Long-term memory for agents",
        "kind": "official_markdown",
        "local_file": "参考文献/长期记忆基线对比参考文献/008_langmem_readme.md",
        "url": "https://github.com/langchain-ai/langmem",
    },
    "009": {
        "title": "Zep: A Temporal Knowledge Graph Architecture for Agent Memory",
        "kind": "paper_pdf",
        "local_file": "参考文献/长期记忆基线对比参考文献/009_zep_rasmussen2025.pdf",
        "url": "https://arxiv.org/abs/2501.13956",
    },
    "010": {
        "title": "A-MEM: Agentic Memory for LLM Agents",
        "kind": "paper_pdf",
        "local_file": "参考文献/长期记忆基线对比参考文献/010_amem_xu2025.pdf",
        "url": "https://arxiv.org/abs/2502.12110",
    },
    "011": {
        "title": "Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory",
        "kind": "paper_pdf",
        "local_file": "参考文献/长期记忆基线对比参考文献/011_mem0_chhikara2025.pdf",
        "url": "https://arxiv.org/abs/2504.19413",
    },
    "012": {
        "title": "MIRIX: Multi-Agent Memory System for LLM-Based Agents",
        "kind": "paper_pdf",
        "local_file": "参考文献/长期记忆基线对比参考文献/012_mirix_wang2025.pdf",
        "url": "https://arxiv.org/abs/2507.07957",
    },
    "013": {
        "title": "What is Memobase?",
        "kind": "official_html",
        "local_file": "参考文献/长期记忆基线对比参考文献/013_memobase_introduction.html",
        "url": "https://docs.memobase.io/introduction",
    },
    "014": {
        "title": "Memobase LoCoMo benchmark experiment README",
        "kind": "official_markdown",
        "local_file": "参考文献/长期记忆基线对比参考文献/014_memobase_locomo_benchmark.md",
        "url": "https://github.com/memodb-io/memobase/blob/main/docs/experiments/locomo-benchmark/README.md",
    },
    "015": {
        "title": "memU GitHub README",
        "kind": "official_markdown",
        "local_file": "参考文献/长期记忆基线对比参考文献/015_memu_readme.md",
        "url": "https://github.com/NevaMind-AI/memU",
    },
    "016": {
        "title": "MemOS: A Memory OS for AI System",
        "kind": "paper_pdf",
        "local_file": "参考文献/长期记忆基线对比参考文献/016_memos_li2025.pdf",
        "url": "https://arxiv.org/abs/2507.03724",
    },
}

METHOD_REFERENCES: dict[str, list[str]] = {
    "no_long_term_memory": [],
    "vector_memory": ["002"],
    "flat_summary_memory": ["002"],
    "naive_graph_memory": ["003"],
    "rag_chunk_memory": ["002"],
    "graph_rag_memory": ["003"],
    "light_rag_memory": ["004"],
    "hippo_rag2_memory": ["005"],
    "hypergraph_rag_memory": ["006"],
    "openai_memory": ["007"],
    "langmem_memory": ["008"],
    "zep_memory": ["009"],
    "amem_memory": ["010"],
    "mem0_memory": ["011"],
    "mem0_graph_memory": ["011"],
    "mirix_memory": ["012"],
    "memobase_memory": ["013", "014"],
    "memu_memory": ["015"],
    "memos_memory": ["016"],
    "mem0_zep_memory": ["009", "011"],
    "hypergraph_proxy": ["006"],
    "clarks_nutcracker_graph": [],
}


def build_comparison_protocol_metadata(methods: tuple[str, ...]) -> dict[str, Any]:
    grouped = {
        group_name: [method for method in group_methods if method in methods]
        for group_name, group_methods in BASELINE_GROUPS.items()
    }
    core_local = [method for method in CORE_LOCAL_BASELINE_METHODS if method in methods]
    proxy_extension = [method for method in PROXY_EXTENSION_METHODS if method in methods]
    literature_only = [method for method in LITERATURE_ONLY_METHODS if method not in methods]
    available_method_catalog = {
        method: {
            "description": METHOD_DESCRIPTIONS.get(method, ""),
            "references": METHOD_REFERENCES.get(method, []),
            "is_core_local": method in CORE_LOCAL_BASELINE_METHODS,
            "is_proxy_extension": method in NON_OFFICIAL_PROXY_EXTENSION_METHODS,
            "has_official_adapter": method in OFFICIAL_BASELINE_METHODS,
            "has_literature_reference": method in LITERATURE_ONLY_METHODS,
            "selected": method in methods,
        }
        for method in tuple(dict.fromkeys((*CORE_LOCAL_BASELINE_METHODS, *BASELINE_METHODS)))
    }
    return {
        **HYPERMEM_REFERENCE_PROTOCOL,
        "default_execution_methods": list(CORE_LOCAL_BASELINE_METHODS),
        "available_proxy_extension_methods": list(NON_OFFICIAL_PROXY_EXTENSION_METHODS),
        "available_official_adapter_methods": list(OFFICIAL_BASELINE_METHODS),
        "literature_reference_methods": list(LITERATURE_ONLY_METHODS),
        "selected_methods": list(methods),
        "comparison_layers": {
            "core_local": core_local,
            "official_adapter": [method for method in OFFICIAL_BASELINE_METHODS if method in methods],
            "proxy_extension": [method for method in NON_OFFICIAL_PROXY_EXTENSION_METHODS if method in methods],
            "literature_only": literature_only,
        },
        "baseline_groups": grouped,
        "method_descriptions": {method: METHOD_DESCRIPTIONS.get(method, "") for method in methods},
        "available_method_catalog": available_method_catalog,
        "reference_manifest": "参考文献/长期记忆基线对比参考文献/baseline_reference_manifest.json",
        "method_references": {method: METHOD_REFERENCES.get(method, []) for method in methods},
        "reference_catalog": {
            reference_id: REFERENCE_CATALOG[reference_id]
            for reference_id in sorted({reference_id for method in methods for reference_id in METHOD_REFERENCES.get(method, [])})
            if reference_id in REFERENCE_CATALOG
        },
    }
