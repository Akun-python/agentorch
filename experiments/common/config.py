from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


KNOWN_VARIANTS = (
    "single_agent_basic",
    "single_agent_long_context",
    "multi_agent_no_elephant",
    "multi_agent_no_seagull",
    "multi_agent_no_long_horizon",
    "multi_agent_no_compression",
    "multi_agent_naive_memory",
    "multi_agent_plain_logs",
    "full_framework",
)


class TaskSpec(BaseModel):
    task_id: str
    instruction: str
    benchmark_id: str | None = None
    benchmark_name: str | None = None
    benchmark_split: str | None = None
    benchmark_sample_id: str | None = None
    expected_capabilities: List[str] = Field(default_factory=list)
    must_use_tools: List[str] = Field(default_factory=list)
    evaluation_type: Literal["heuristic", "judge", "trace", "memory"] = "heuristic"
    rubric: Dict[str, Any] = Field(default_factory=dict)
    live_web_required: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExperimentConfig(BaseModel):
    experiment_name: str
    variant_name: str = "full_framework"
    model_name: str = "mock:tool"
    judge_model_name: Optional[str] = None
    max_steps: int = 8
    prompt_budget: int = 12000
    enable_elephant_attention: bool = True
    enable_seagull_memory: bool = True
    enable_long_horizon_attention: bool = True
    enable_context_compression: bool = True
    enable_observability: bool = True
    enable_multi_agent: bool = True
    enable_retrieval: bool = True
    enable_live_web_search: bool = True
    seed: int = 7
    task_limit: Optional[int] = None
    repeat_count: int = 1
    output_dir: Path = Path("experiments/results")
    execution_tier: Literal["local_slice", "official_benchmark"] = "local_slice"
    benchmark_split: str = "local_dev_slice"
    results_schema_version: str = "2.0"
    output_tag: Optional[str] = None
    use_stable_output_dir: bool = False
    retry_failed: int = 0
    agent_count: int = 2
    history_length: Optional[int] = None

    @classmethod
    def for_variant(
        cls,
        *,
        experiment_name: str,
        variant_name: str,
        model_name: str,
        judge_model_name: str | None,
        prompt_budget: int,
        task_limit: int | None,
        repeat_count: int,
        output_dir: Path,
        enable_live_web_search: bool,
        seed: int,
        execution_tier: Literal["local_slice", "official_benchmark"] = "local_slice",
        benchmark_split: str = "local_dev_slice",
        output_tag: str | None = None,
        use_stable_output_dir: bool = False,
        retry_failed: int = 0,
        agent_count: int = 2,
        history_length: int | None = None,
    ) -> "ExperimentConfig":
        config = cls(
            experiment_name=experiment_name,
            variant_name=variant_name,
            model_name=model_name,
            judge_model_name=judge_model_name,
            prompt_budget=prompt_budget,
            task_limit=task_limit,
            repeat_count=repeat_count,
            output_dir=output_dir,
            enable_live_web_search=enable_live_web_search,
            seed=seed,
            execution_tier=execution_tier,
            benchmark_split=benchmark_split,
            output_tag=output_tag,
            use_stable_output_dir=use_stable_output_dir,
            retry_failed=retry_failed,
            agent_count=agent_count,
            history_length=history_length,
        )
        if variant_name == "single_agent_basic":
            config.enable_multi_agent = False
            config.enable_retrieval = False
            config.enable_elephant_attention = False
            config.enable_long_horizon_attention = False
            config.enable_context_compression = False
            config.enable_seagull_memory = False
        elif variant_name == "single_agent_long_context":
            config.enable_multi_agent = False
            config.enable_retrieval = True
            config.enable_elephant_attention = False
            config.enable_long_horizon_attention = True
            config.enable_context_compression = False
            config.enable_seagull_memory = False
        elif variant_name == "multi_agent_no_elephant":
            config.enable_elephant_attention = False
        elif variant_name == "multi_agent_no_seagull":
            config.enable_seagull_memory = False
        elif variant_name == "multi_agent_no_long_horizon":
            config.enable_long_horizon_attention = False
        elif variant_name == "multi_agent_no_compression":
            config.enable_context_compression = False
        elif variant_name == "multi_agent_naive_memory":
            config.enable_seagull_memory = False
        elif variant_name == "multi_agent_plain_logs":
            config.enable_observability = False
        elif variant_name != "full_framework":
            raise ValueError(f"Unsupported variant '{variant_name}'.")
        return config


class RunRecord(BaseModel):
    experiment_name: str
    variant_name: str
    model_name: str
    seed: int
    repeat_index: int = 0
    results_schema_version: str = "2.0"
    task_id: str
    benchmark_id: str | None = None
    benchmark_name: str | None = None
    benchmark_split: str | None = None
    benchmark_sample_id: str | None = None
    run_id: str
    thread_id: str
    status: str
    success: bool
    final_text: str
    quality_score: float
    token_usage: int
    latency_ms: int
    tool_call_count: int
    delegation_depth: int
    memory_hit_count: int
    budget_overflow: bool
    todo_summary: Dict[str, Any] = Field(default_factory=dict)
    sqlite_path: Optional[str] = None
    live_web_available: bool = False
    skip_reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
