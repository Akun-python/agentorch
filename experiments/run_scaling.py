from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.common.config import ExperimentConfig
from experiments.common.model_presets import REAL_SCALING_MODEL
from experiments.common.runner import run_experiment_sync
from experiments.formal.protocol import FORMAL_PROTOCOL, load_protocol_tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="Run agent-count scaling experiments for AgentOrch")
    parser.add_argument("--experiment", choices=["rq1_long_horizon_tasks"], default="rq1_long_horizon_tasks")
    parser.add_argument("--model", default=REAL_SCALING_MODEL)
    parser.add_argument("--agent-counts", default="1,2,4")
    parser.add_argument("--seeds", default="7,11,19,23,29")
    parser.add_argument("--task-limit", type=int, default=None)
    parser.add_argument("--budget", type=int, default=12000)
    parser.add_argument("--output-dir", type=Path, default=Path("experiments/results_formal"))
    args = parser.parse_args()

    protocol = FORMAL_PROTOCOL[args.experiment]
    tasks = load_protocol_tasks(args.experiment)
    seeds = [int(item.strip()) for item in args.seeds.split(",") if item.strip()]
    agent_counts = [int(item.strip()) for item in args.agent_counts.split(",") if item.strip()]

    for agent_count in agent_counts:
        variant = "single_agent_basic" if agent_count == 1 else "full_framework"
        for seed in seeds:
            config = ExperimentConfig.for_variant(
                experiment_name=args.experiment,
                variant_name=variant,
                model_name=args.model,
                judge_model_name=None,
                prompt_budget=args.budget,
                task_limit=args.task_limit,
                repeat_count=1,
                output_dir=args.output_dir,
                enable_live_web_search=False,
                seed=seed,
                execution_tier="official_benchmark",
                benchmark_split=protocol["split"],
                output_tag=f"scaling_agents_{agent_count}",
                use_stable_output_dir=True,
                retry_failed=1,
                agent_count=agent_count,
            )
            run_experiment_sync(config=config, tasks=tasks, annotate_record=protocol["annotate"])


if __name__ == "__main__":
    main()
