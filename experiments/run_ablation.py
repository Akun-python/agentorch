from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.common.config import ExperimentConfig
from experiments.common.model_presets import REAL_ABLATION_MODELS
from experiments.common.runner import run_experiment_sync
from experiments.formal.protocol import FORMAL_PROTOCOL, load_protocol_tasks


ABLATION_VARIANTS = {
    "rq1_long_horizon_tasks": ["full_framework", "single_agent_basic", "multi_agent_no_elephant", "multi_agent_plain_logs"],
    "rq2_elephant_attention": ["full_framework", "single_agent_long_context", "multi_agent_no_elephant"],
    "rq3_seagull_memory": ["full_framework", "multi_agent_no_seagull", "multi_agent_naive_memory"],
    "rq4_budget_robustness": ["full_framework", "multi_agent_no_long_horizon", "multi_agent_no_compression"],
    "rq5_observability": ["full_framework", "multi_agent_plain_logs"],
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run formal ablations for AgentOrch")
    parser.add_argument("--experiment", choices=list(ABLATION_VARIANTS), required=True)
    parser.add_argument("--models", default=",".join(REAL_ABLATION_MODELS))
    parser.add_argument("--seeds", default="7,11,19,23,29")
    parser.add_argument("--task-limit", type=int, default=None)
    parser.add_argument("--budget", type=int, default=12000)
    parser.add_argument("--output-dir", type=Path, default=Path("experiments/results_formal"))
    args = parser.parse_args()

    protocol = FORMAL_PROTOCOL[args.experiment]
    tasks = load_protocol_tasks(args.experiment)
    models = [item.strip() for item in args.models.split(",") if item.strip()]
    seeds = [int(item.strip()) for item in args.seeds.split(",") if item.strip()]

    for variant in ABLATION_VARIANTS[args.experiment]:
        for model in models:
            for seed in seeds:
                config = ExperimentConfig.for_variant(
                    experiment_name=args.experiment,
                    variant_name=variant,
                    model_name=model,
                    judge_model_name=None,
                    prompt_budget=args.budget,
                    task_limit=args.task_limit,
                    repeat_count=1,
                    output_dir=args.output_dir,
                    enable_live_web_search=False,
                    seed=seed,
                    execution_tier="official_benchmark",
                    benchmark_split=protocol["split"],
                    output_tag="formal_ablation",
                    use_stable_output_dir=True,
                    retry_failed=1,
                )
                run_experiment_sync(config=config, tasks=tasks, annotate_record=protocol["annotate"])


if __name__ == "__main__":
    main()
