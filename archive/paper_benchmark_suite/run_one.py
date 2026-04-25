from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.common.cli import build_parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    module = __import__(f"experiments.{args.experiment}.run", fromlist=["run_cli"])
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
