from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from experiments.common.config import ExperimentConfig
from experiments.common.runner import run_experiment_sync
from .evaluate import annotate


def run_cli(*, variant: str, model: str, judge_model: str | None, task_limit: int | None, repeat: int, budget: int, output_dir: Path, live_web: bool, seed: int):
    config = ExperimentConfig.for_variant(
        experiment_name="rq4_budget_robustness",
        variant_name=variant,
        model_name=model,
        judge_model_name=judge_model,
        prompt_budget=budget,
        task_limit=task_limit,
        repeat_count=repeat,
        output_dir=output_dir,
        enable_live_web_search=live_web,
        seed=seed,
    )
    return run_experiment_sync(config=config, tasks_path=Path(__file__).with_name("tasks.jsonl"), annotate_record=annotate)


if __name__ == "__main__":
    from experiments.common.cli import build_local_parser

    parser = build_local_parser()
    args = parser.parse_args()
    run_cli(
        variant=args.variant,
        model=args.model,
        judge_model=args.judge_model,
        task_limit=args.task_limit,
        repeat=args.repeat,
        budget=args.budget,
        output_dir=Path(args.output_dir),
        live_web=args.live_web,
        seed=args.seed,
    )
