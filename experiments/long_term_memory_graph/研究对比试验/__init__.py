"""E2 强基线对比实验入口。"""

__all__ = ["build_parser", "run_comparison_experiment", "run_from_args"]


def build_parser(*args, **kwargs):
    """懒加载 parser，避免导入包时提前加载 runner。"""

    from .runner import build_parser as _build_parser

    return _build_parser(*args, **kwargs)


def run_comparison_experiment(*args, **kwargs):
    """懒加载对比实验函数。"""

    from .runner import run_comparison_experiment as _run_comparison_experiment

    return _run_comparison_experiment(*args, **kwargs)


def run_from_args(*args, **kwargs):
    """懒加载 argparse 入口。"""

    from .runner import run_from_args as _run_from_args

    return _run_from_args(*args, **kwargs)
