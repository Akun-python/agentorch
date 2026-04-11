from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.common.cli import KNOWN_EXPERIMENTS
from experiments.common.config import ExperimentConfig
from experiments.common.model_presets import REAL_FORMAL_MODELS
from experiments.common.runner import run_experiment_sync
from experiments.formal.protocol import FORMAL_PROTOCOL, load_protocol_tasks


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run formal benchmark experiments for AgentOrch")
    parser.add_argument("--experiment", choices=KNOWN_EXPERIMENTS, default=None)
    parser.add_argument("--models", default=",".join(REAL_FORMAL_MODELS))
    parser.add_argument("--variants", default="full_framework")
    parser.add_argument("--seeds", default="7,11,19")
    parser.add_argument("--task-limit", type=int, default=None)
    parser.add_argument("--budget", type=int, default=12000)
    parser.add_argument("--output-dir", type=Path, default=Path("experiments/results_formal"))
    parser.add_argument("--live-web", action="store_true")
    args = parser.parse_args()

    experiments = [args.experiment] if args.experiment else list(KNOWN_EXPERIMENTS)
    models = _parse_csv(args.models)
    variants = _parse_csv(args.variants)
    seeds = [int(item) for item in _parse_csv(args.seeds)]

    for experiment_name in experiments:
        protocol = FORMAL_PROTOCOL[experiment_name]
        tasks = load_protocol_tasks(experiment_name)
        for variant in variants:
            for model in models:
                for seed in seeds:
                    config = ExperimentConfig.for_variant(
                        experiment_name=experiment_name,
                        variant_name=variant,
                        model_name=model,
                        judge_model_name=None,
                        prompt_budget=args.budget,
                        task_limit=args.task_limit,
                        repeat_count=1,
                        output_dir=args.output_dir,
                        enable_live_web_search=args.live_web,
                        seed=seed,
                        execution_tier="official_benchmark",
                        benchmark_split=protocol["split"],
                        output_tag="formal_benchmark",
                        use_stable_output_dir=True,
                        retry_failed=1,
                    )
                    run_experiment_sync(config=config, tasks=tasks, annotate_record=protocol["annotate"])


if __name__ == "__main__":
    main()
