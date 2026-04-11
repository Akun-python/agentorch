from __future__ import annotations

import argparse
from pathlib import Path

from .config import KNOWN_VARIANTS


KNOWN_EXPERIMENTS = (
    "rq1_long_horizon_tasks",
    "rq2_elephant_attention",
    "rq3_seagull_memory",
    "rq4_budget_robustness",
    "rq5_observability",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AgentOrch paper experiments runner")
    parser.add_argument("--experiment", choices=KNOWN_EXPERIMENTS, required=True)
    _add_shared_arguments(parser)
    return parser


def build_local_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AgentOrch single experiment runner")
    _add_shared_arguments(parser)
    return parser


def _add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--variant", choices=KNOWN_VARIANTS, default="full_framework")
    parser.add_argument("--model", default="mock:tool")
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--task-limit", type=int, default=None)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--budget", type=int, default=12000)
    parser.add_argument("--output-dir", type=Path, default=Path("experiments/results"))
    parser.add_argument("--live-web", action="store_true")
    parser.add_argument("--seed", type=int, default=7)
