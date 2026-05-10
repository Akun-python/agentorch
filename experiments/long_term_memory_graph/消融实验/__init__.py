"""E4 消融与参数敏感性实验入口。"""

from .runner import build_parser, run_ablation_experiment, run_from_args

__all__ = ["build_parser", "run_ablation_experiment", "run_from_args"]
