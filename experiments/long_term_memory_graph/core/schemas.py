from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..api.models import MemoryCapsuleCandidate

# 问题类型对齐 LoCoMo / LongMemEval 风格的长期记忆问答切片。
QUESTION_TYPES: tuple[str, ...] = ("Single-hop", "Multi-hop", "Temporal", "Open Domain")

# 主方法代表本文机制，其他方法用于对比或消融。
MAIN_METHOD = "clarks_nutcracker_graph"

OFFICIAL_BASELINE_METHODS: tuple[str, ...] = (
    "langmem_memory",
    "mem0_memory",
    "zep_memory",
)

PAPER_COMPARISON_METHODS: tuple[str, ...] = (
    "langmem_memory",
    "mem0_memory",
    "zep_memory",
    MAIN_METHOD,
)

CORE_LOCAL_BASELINE_METHODS: tuple[str, ...] = (
    "no_long_term_memory",
    "vector_memory",
    "flat_summary_memory",
    "naive_graph_memory",
    MAIN_METHOD,
)

BASELINE_METHODS: tuple[str, ...] = (
    "rag_chunk_memory",
    "graph_rag_memory",
    "light_rag_memory",
    "hippo_rag2_memory",
    "hypergraph_rag_memory",
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
    MAIN_METHOD,
)

PROXY_EXTENSION_METHODS: tuple[str, ...] = tuple(method for method in BASELINE_METHODS if method not in CORE_LOCAL_BASELINE_METHODS)

NON_OFFICIAL_PROXY_EXTENSION_METHODS: tuple[str, ...] = tuple(
    method for method in PROXY_EXTENSION_METHODS if method not in OFFICIAL_BASELINE_METHODS
)

LITERATURE_ONLY_METHODS: tuple[str, ...] = (
    "graph_rag_memory",
    "light_rag_memory",
    "hippo_rag2_memory",
    "hypergraph_rag_memory",
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
)

LEGACY_BASELINE_METHODS: tuple[str, ...] = (
    "no_long_term_memory",
    "vector_memory",
    "flat_summary_memory",
    "naive_graph_memory",
    "mem0_zep_memory",
    "hypergraph_proxy",
)

SUPPORTED_BASELINE_METHODS: tuple[str, ...] = tuple(dict.fromkeys((*BASELINE_METHODS, *LEGACY_BASELINE_METHODS)))

ABLATION_VARIANTS: tuple[str, ...] = (
    "full",
    "wo_scene_match",
    "wo_temporal_edges",
    "wo_revision_edges",
    "wo_conflict_suppression",
    "wo_stale_suppression",
    "graph_no_policy",
    "multi_level_topk",
    "scene_weight_0_3",
    "scene_weight_1_2",
    "topk_small",
    "topk_large",
)

REQUIRED_CSV_FIELDS: tuple[str, ...] = (
    "case_id",
    "question_type",
    "method",
    "source_boundary",
    "is_proxy",
    "answer",
    "standard_answer",
    "judge_score",
    "judge_raw_output",
    "target_capsule_hit",
    "target_relation_hit",
    "input_tokens",
    "output_tokens",
    "returned_node_count",
    "returned_edge_count",
    "latency_ms",
    "run_round",
)

EXTRA_CSV_FIELDS: tuple[str, ...] = (
    "suite",
    "variant",
    "judge_backend",
    "agentorch_run_id",
    "thread_id",
    "returned_capsule_ids",
    "returned_relation_types",
    "suppressed_stale_nodes",
    "suppressed_conflict_nodes",
    "case_tags",
    "detail_lookup_capsule_ids",
    "latency_breakdown_json",
    "stale_node_injection_rate",
    "conflict_resolution_success",
    "evidence_completeness",
    "capsule_recall_at_k",
    "revision_hit_rate",
    "returned_memory_usefulness",
    "returned_evidence_count",
    "detail_lookup_latency_ms",
    "detail_lookup_hit_count",
    "detail_lookup_missing_count",
    "relative_tokens",
    "answer_total_tokens",
    "answer_duration_ms",
    "answer_finish_reason",
    "judge_prompt_tokens",
    "judge_completion_tokens",
    "judge_total_tokens",
    "judge_duration_ms",
    "embedding_request_count",
    "embedding_text_count",
    "embedding_latency_ms",
)


@dataclass(frozen=True)
class ExperimentCase:
    """单条长期记忆实验样本。

    capsues 是该样本的局部记忆图，target_* 字段用于自动计算命中率。
    """

    case_id: str
    question_type: str
    query: str
    standard_answer: str
    capsules: tuple[MemoryCapsuleCandidate, ...]
    target_capsule_ids: tuple[str, ...]
    target_relation_types: tuple[str, ...] = ()
    revision_target_ids: tuple[str, ...] = ()
    stale_capsule_ids: tuple[str, ...] = ()
    conflict_loser_ids: tuple[str, ...] = ()
    detail_lookup_capsule_ids: tuple[str, ...] = ()
    knowledge_scope: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    case_tags: tuple[str, ...] = ()
    token_budget: int | None = None
    notes: str = ""


@dataclass(frozen=True)
class ExperimentRunConfig:
    """一轮实验套件的完整运行配置。"""

    suite: str
    methods: tuple[str, ...]
    output_dir: Path
    case_limit: int | None = None
    case_offset: int = 0
    shard_id: int | None = None
    num_shards: int | None = None
    runs: int = 1
    seed: int = 0
    dataset_path: Path | None = None
    resume: bool = False
    judge_backend: str = "deterministic_probe"
    model_backend: str = "agentorch_probe"
    model_name: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    env_file: Path | None = Path(".env")
    load_env: bool = True
    overwrite_env: bool = False
    max_nodes: int = 12
    max_edges: int = 24
    top_candidates: int = 6
    top_seeds: int = 3
    bootstrap_samples: int = 300
    manual_review_sample_size: int = 8
    second_judge_sample_size: int = 8
    judge_model_backend: str | None = None
    judge_model_name: str | None = None
    sweep_parameters: dict[str, list[float | int]] | None = None
    protocol_metadata: dict[str, Any] | None = None
    paper_mode: bool = False
    strict_official_baselines: bool = False
    required_token_reference_method: str | None = None


@dataclass
class RetrievalResult:
    """某个记忆方法对单个 case 的召回结果。"""

    method: str
    variant: str
    prompt_summary: str
    returned_capsule_ids: list[str] = field(default_factory=list)
    returned_relation_types: list[str] = field(default_factory=list)
    returned_edge_keys: list[str] = field(default_factory=list)
    suppressed_stale_nodes: list[str] = field(default_factory=list)
    suppressed_conflict_nodes: list[str] = field(default_factory=list)
    detail_lookup_capsule_ids: list[str] = field(default_factory=list)
    detail_lookup_hit_count: int = 0
    detail_lookup_missing_count: int = 0
    detail_lookup_latency_ms: float = 0.0
    latency_breakdown: dict[str, float] = field(default_factory=dict)
    latency_ms: float = 0.0
    embedding_request_count: int = 0
    embedding_text_count: int = 0
    embedding_latency_ms: float = 0.0
    source_boundary: str | None = None
    is_proxy: bool | None = None


@dataclass
class AgentAnswer:
    """AgentTorch 生成答案后的可审计记录。"""

    answer: str
    input_tokens: int
    output_tokens: int
    agentorch_run_id: str
    thread_id: str
    finish_reason: str | None = None
    total_tokens: int = 0
    duration_ms: float = 0.0


@dataclass
class JudgeResult:
    """裁判模型或确定性裁判给出的评分结果。"""

    score: float
    raw_output: dict[str, Any]
    model_backend: str | None = None
    model_name: str | None = None
    duration_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ExperimentRecord:
    """写入 CSV/JSONL 的最小实验记录。"""

    suite: str
    case_id: str
    question_type: str
    method: str
    variant: str
    source_boundary: str
    is_proxy: bool
    answer: str
    standard_answer: str
    judge_score: float
    judge_raw_output: str
    target_capsule_hit: bool
    target_relation_hit: bool
    input_tokens: int
    output_tokens: int
    returned_node_count: int
    returned_edge_count: int
    latency_ms: float
    run_round: int
    judge_backend: str
    agentorch_run_id: str
    thread_id: str
    returned_capsule_ids: str
    returned_relation_types: str
    suppressed_stale_nodes: str
    suppressed_conflict_nodes: str
    case_tags: str
    detail_lookup_capsule_ids: str
    latency_breakdown_json: str
    stale_node_injection_rate: float
    conflict_resolution_success: float
    evidence_completeness: float
    capsule_recall_at_k: float
    revision_hit_rate: float
    returned_memory_usefulness: float
    returned_evidence_count: int
    detail_lookup_latency_ms: float
    detail_lookup_hit_count: int
    detail_lookup_missing_count: int
    relative_tokens: float = 0.0
    answer_total_tokens: int = 0
    answer_duration_ms: float = 0.0
    answer_finish_reason: str = ""
    judge_prompt_tokens: int = 0
    judge_completion_tokens: int = 0
    judge_total_tokens: int = 0
    judge_duration_ms: float = 0.0
    embedding_request_count: int = 0
    embedding_text_count: int = 0
    embedding_latency_ms: float = 0.0


@dataclass
class ExperimentSuiteResult:
    """实验套件返回给上层 runner 的内存结果。"""

    manifest: dict[str, Any]
    records: list[ExperimentRecord]
    aggregates: list[dict[str, Any]]
