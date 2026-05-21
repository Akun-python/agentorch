from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    # 兼容直接运行本文件的情况。
    project_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(project_root))
    from experiments.long_term_memory_graph.core import ABLATION_VARIANTS, ExperimentRunConfig, run_suite
    from experiments.long_term_memory_graph.消融实验.protocol import build_ablation_protocol_metadata
else:
    from ..core import ABLATION_VARIANTS, ExperimentRunConfig, run_suite
    from .protocol import build_ablation_protocol_metadata


def run_ablation_experiment(
    *,
    output_dir: str | Path,
    variants: tuple[str, ...] = ABLATION_VARIANTS,
    case_limit: int | None = None,
    case_offset: int = 0,
    shard_id: int | None = None,
    num_shards: int | None = None,
    runs: int = 1,
    seed: int = 0,
    dataset_path: str | Path | None = None,
    resume: bool = False,
    judge_backend: str = "deterministic_probe",
    judge_model_backend: str | None = None,
    judge_model_name: str | None = None,
    model_backend: str = "agentorch_probe",
    model_name: str | None = None,
    embedding_model: str | None = None,
    embedding_dimensions: int | None = None,
    env_file: str | Path | None = ".env",
    load_env: bool = True,
    overwrite_env: bool = False,
    sweep_parameters: dict[str, list[float | int]] | None = None,
) -> dict[str, object]:
    """运行 E4 消融与参数敏感性实验。"""

    resolved_sweeps = sweep_parameters or _default_parameter_sweeps()
    result = run_suite(
        ExperimentRunConfig(
            suite="ablation",
            methods=variants,
            output_dir=Path(output_dir),
            case_limit=case_limit,
            case_offset=case_offset,
            shard_id=shard_id,
            num_shards=num_shards,
            runs=runs,
            seed=seed,
            dataset_path=Path(dataset_path) if dataset_path else None,
            resume=resume,
            judge_backend=judge_backend,
            judge_model_backend=judge_model_backend,
            judge_model_name=judge_model_name,
            model_backend=model_backend,
            model_name=model_name,
            embedding_model=embedding_model,
            embedding_dimensions=embedding_dimensions,
            env_file=Path(env_file) if env_file else None,
            load_env=load_env,
            overwrite_env=overwrite_env,
            sweep_parameters=resolved_sweeps,
            protocol_metadata=build_ablation_protocol_metadata(variants, resolved_sweeps),
        )
    )
    return result.manifest


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """注册 ablate 子命令。"""

    parser = subparsers.add_parser(
        "ablate",
        help="运行 E4：场景索引、时间边、修正边、冲突/陈旧抑制和 top-k 参数消融。",
    )
    parser.add_argument("--variants", default=",".join(ABLATION_VARIANTS))
    _add_common_args(parser, default_output="artifacts/long_term_memory_graph/ablation")
    parser.set_defaults(handler=run_from_args)


def run_from_args(args: argparse.Namespace) -> dict[str, object]:
    """把 argparse 参数转成消融实验函数调用。"""

    variants = tuple(item.strip() for item in args.variants.split(",") if item.strip())
    return run_ablation_experiment(
        output_dir=args.output_dir,
        variants=variants,
        case_limit=args.case_limit,
        case_offset=args.case_offset,
        shard_id=args.shard_id,
        num_shards=args.num_shards,
        runs=args.runs,
        seed=args.seed,
        dataset_path=args.dataset_path,
        resume=args.resume,
        judge_backend=args.judge_backend,
        judge_model_backend=args.judge_model_backend,
        judge_model_name=args.judge_model,
        model_backend=args.model_backend,
        model_name=args.model,
        embedding_model=args.embedding_model,
        embedding_dimensions=args.embedding_dimensions,
        env_file=args.env_file,
        load_env=not args.no_env_file,
        overwrite_env=args.overwrite_env,
        sweep_parameters=_parse_sweeps(args),
    )


def _add_common_args(parser: argparse.ArgumentParser, *, default_output: str) -> None:
    """消融实验通用 CLI 参数和参数扫描入口。"""

    parser.add_argument("--output-dir", default=default_output)
    parser.add_argument("--case-limit", type=int, default=None)
    parser.add_argument("--case-offset", type=int, default=0)
    parser.add_argument("--shard-id", type=int, default=None)
    parser.add_argument("--num-shards", type=int, default=None)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--dataset-path", default=None)
    parser.add_argument("--resume", action="store_true", help="从现有输出目录续跑，跳过已完成的 case/method/run_round。")
    parser.add_argument("--judge-backend", default="deterministic_probe")
    parser.add_argument("--judge-model-backend", default=None, choices=["openai", "openai_http"])
    parser.add_argument("--judge-model", default=None, help="真实 judge 使用的模型名；也可由 OPENAI_MODEL/MODEL_NAME 提供。")
    parser.add_argument("--model-backend", default="agentorch_probe")
    parser.add_argument("--model", default=None, help="真实 API 后端使用的模型名；也可由 OPENAI_MODEL/MODEL_NAME 提供。")
    parser.add_argument("--embedding-model", default=None, help="真实 embedding 使用的模型名；也可由 OPENAI_EMBEDDING_MODEL 提供。")
    parser.add_argument("--embedding-dimensions", type=int, default=None, help="embedding 维度。")
    parser.add_argument("--env-file", default=".env", help="真实 API 后端加载的 env 文件路径；默认使用当前目录 .env。")
    parser.add_argument("--no-env-file", action="store_true", help="禁用 env 文件加载，仅使用当前进程环境变量。")
    parser.add_argument("--overwrite-env", action="store_true", help="允许 env 文件覆盖当前进程已有环境变量。")
    parser.add_argument("--sweep-top-candidates", default="4,6,10")
    parser.add_argument("--sweep-top-seeds", default="2,3,5")
    parser.add_argument("--sweep-max-nodes", default="6,12,18")
    parser.add_argument("--sweep-max-edges", default="10,24,36")
    parser.add_argument("--sweep-scene-weight", default="0.3,0.9,1.2")
    parser.add_argument("--sweep-stale-weight", default="0.0,1.0,1.5")
    parser.add_argument("--sweep-conflict-weight", default="0.0,0.35,0.8")


def _parse_csv_numbers(value: str) -> list[float | int]:
    """解析命令行传入的逗号分隔数值。"""

    items = []
    for raw in value.split(","):
        raw = raw.strip()
        if not raw:
            continue
        items.append(float(raw) if "." in raw else int(raw))
    return items


def _parse_sweeps(args: argparse.Namespace) -> dict[str, list[float | int]]:
    """把多个 sweep 参数整理成统一字典。"""

    return {
        "top_candidates": _parse_csv_numbers(args.sweep_top_candidates),
        "top_seeds": _parse_csv_numbers(args.sweep_top_seeds),
        "max_nodes": _parse_csv_numbers(args.sweep_max_nodes),
        "max_edges": _parse_csv_numbers(args.sweep_max_edges),
        "scene_match_weight": _parse_csv_numbers(args.sweep_scene_weight),
        "stale_penalty_weight": _parse_csv_numbers(args.sweep_stale_weight),
        "conflict_penalty_weight": _parse_csv_numbers(args.sweep_conflict_weight),
    }


def _default_parameter_sweeps() -> dict[str, list[float | int]]:
    """默认参数扫描范围。"""

    return {
        "top_candidates": [4, 6, 10],
        "top_seeds": [2, 3, 5],
        "max_nodes": [6, 12, 18],
        "max_edges": [10, 24, 36],
        "scene_match_weight": [0.3, 0.9, 1.2],
        "stale_penalty_weight": [0.0, 1.0, 1.5],
        "conflict_penalty_weight": [0.0, 0.35, 0.8],
    }


def main(argv: Sequence[str] | None = None) -> int:
    """支持 `python runner.py` 直接运行。"""

    parser = argparse.ArgumentParser(description="直接运行 E4 消融与参数敏感性实验。")
    parser.add_argument("--variants", default=",".join(ABLATION_VARIANTS))
    _add_common_args(parser, default_output="artifacts/long_term_memory_graph/ablation")
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = run_from_args(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
