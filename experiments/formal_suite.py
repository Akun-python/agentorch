from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.run_ablation import ABLATION_VARIANTS
from experiments.common.config import ExperimentConfig
from experiments.common.model_presets import REAL_ABLATION_MODELS, REAL_FORMAL_MODELS, REAL_SCALING_MODEL
from experiments.common.runner import run_experiment_sync
from experiments.formal.protocol import FORMAL_PROTOCOL, load_protocol_tasks


def main() -> None:
    output_dir = Path("experiments/results_formal")
    models = list(REAL_FORMAL_MODELS)
    seeds = [7, 11, 19]
    budget_grid = [2500, 4000, 6000, 9000, 12000]

    for experiment_name, protocol in FORMAL_PROTOCOL.items():
        tasks = load_protocol_tasks(experiment_name)
        variants = ABLATION_VARIANTS.get(experiment_name, ["full_framework"])
        if experiment_name == "rq4_budget_robustness":
            for budget in budget_grid:
                for variant in variants:
                    for model in REAL_ABLATION_MODELS[:2]:
                        for seed in seeds:
                            config = ExperimentConfig.for_variant(
                                experiment_name=experiment_name,
                                variant_name=variant,
                                model_name=model,
                                judge_model_name=None,
                                prompt_budget=budget,
                                task_limit=None,
                                repeat_count=1,
                                output_dir=output_dir,
                                enable_live_web_search=False,
                                seed=seed,
                                execution_tier="official_benchmark",
                                benchmark_split=protocol["split"],
                                output_tag="formal_benchmark",
                                use_stable_output_dir=True,
                                retry_failed=1,
                            )
                            run_experiment_sync(config=config, tasks=tasks, annotate_record=protocol["annotate"])
            continue

        for variant in variants:
            for model in models:
                for seed in seeds:
                    config = ExperimentConfig.for_variant(
                        experiment_name=experiment_name,
                        variant_name=variant,
                        model_name=model,
                        judge_model_name=None,
                        prompt_budget=12000,
                        task_limit=None,
                        repeat_count=1,
                        output_dir=output_dir,
                        enable_live_web_search=False,
                        seed=seed,
                        execution_tier="official_benchmark",
                        benchmark_split=protocol["split"],
                        output_tag="formal_benchmark",
                        use_stable_output_dir=True,
                        retry_failed=1,
                    )
                    run_experiment_sync(config=config, tasks=tasks, annotate_record=protocol["annotate"])

    scaling_tasks = load_protocol_tasks("rq1_long_horizon_tasks")
    for agent_count in (1, 2, 4):
        variant = "single_agent_basic" if agent_count == 1 else "full_framework"
        for seed in seeds:
            config = ExperimentConfig.for_variant(
                experiment_name="rq1_long_horizon_tasks",
                variant_name=variant,
                model_name=REAL_SCALING_MODEL,
                judge_model_name=None,
                prompt_budget=12000,
                task_limit=None,
                repeat_count=1,
                output_dir=output_dir,
                enable_live_web_search=False,
                seed=seed,
                execution_tier="official_benchmark",
                benchmark_split=FORMAL_PROTOCOL["rq1_long_horizon_tasks"]["split"],
                output_tag=f"scaling_agents_{agent_count}",
                use_stable_output_dir=True,
                retry_failed=1,
                agent_count=agent_count,
            )
            run_experiment_sync(config=config, tasks=scaling_tasks, annotate_record=FORMAL_PROTOCOL["rq1_long_horizon_tasks"]["annotate"])


if __name__ == "__main__":
    main()
