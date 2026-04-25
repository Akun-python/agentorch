from __future__ import annotations

import sys
from pathlib import Path

import argparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.common.cli import KNOWN_EXPERIMENTS


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all AgentOrch paper experiments")
    parser.add_argument("--variant", default="full_framework")
    parser.add_argument("--model", default="mock:tool")
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--task-limit", type=int, default=None)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--budget", type=int, default=12000)
    parser.add_argument("--output-dir", type=Path, default=Path("experiments/results"))
    parser.add_argument("--live-web", action="store_true")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    for experiment_name in KNOWN_EXPERIMENTS:
        module = __import__(f"experiments.{experiment_name}.run", fromlist=["run_cli"])
        module.run_cli(
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


if __name__ == "__main__":
    main()
