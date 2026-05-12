from __future__ import annotations

import argparse
import importlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..core.env_config import build_live_model_config, load_experiment_env


def _main_runner():
    return importlib.import_module("experiments.long_term_memory_graph.主模型.runner")


def _comparison_runner():
    return importlib.import_module("experiments.long_term_memory_graph.研究对比试验.runner")


def _ablation_runner():
    return importlib.import_module("experiments.long_term_memory_graph.消融实验.runner")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m experiments.long_term_memory_graph",
        description="Clark's nutcracker inspired long-term memory graph experiment entrypoints.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    _main_runner().build_parser(subparsers)
    _comparison_runner().build_parser(subparsers)
    _ablation_runner().build_parser(subparsers)
    _build_check_env_parser(subparsers)
    _build_full_parser(subparsers)
    return parser


def _build_check_env_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("check-env", help="只检查真实 API 后端的 env 加载链路，不发起模型请求，不输出密钥。")
    parser.add_argument("--model-backend", default="openai_http", choices=["openai", "openai_http", "agentorch_probe"])
    parser.add_argument("--model", default=None, help="真实 API 后端使用的模型名；也可由 OPENAI_MODEL/MODEL_NAME 提供。")
    parser.add_argument("--embedding-model", default=None, help="真实 embedding 使用的模型名；也可由 OPENAI_EMBEDDING_MODEL 提供。")
    parser.add_argument("--embedding-dimensions", type=int, default=None, help="embedding 维度。")
    parser.add_argument("--role", default="model", choices=["model", "judge"], help="检查主模型还是 judge 的 env 配置链路。")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--no-env-file", action="store_true")
    parser.add_argument("--overwrite-env", action="store_true")
    parser.set_defaults(handler=_check_env_from_args)


def _check_env_from_args(args: argparse.Namespace) -> dict[str, Any]:
    load_env = not args.no_env_file
    if args.model_backend == "agentorch_probe":
        report = load_experiment_env(
            env_file=args.env_file,
            model_backend=args.model_backend,
            load_env=False,
            role_prefix="JUDGE" if args.role == "judge" else None,
            overwrite_env=args.overwrite_env,
        )
        return {
            "command": "check-env",
            "role": args.role,
            "model_backend": args.model_backend,
            "embedding_model": args.embedding_model,
            "embedding_dimensions": args.embedding_dimensions,
            "env_file": report.env_file,
            "env_file_exists": report.env_file_exists,
            "env_loaded": False,
            "api_key_present": report.api_key_present,
            "base_url_present": report.base_url_present,
            "model_present": report.model_present,
            "embedding_api_key_present": report.embedding_api_key_present,
            "embedding_base_url_present": report.embedding_base_url_present,
            "embedding_model_present": report.embedding_model_present,
            "secret_values_printed": False,
        }
    config, report = build_live_model_config(
        model_backend=args.model_backend,
        model_name=args.model,
        env_file=args.env_file,
        load_env=load_env,
        role_prefix="JUDGE" if args.role == "judge" else None,
        overwrite_env=args.overwrite_env,
    )
    return {
        "command": "check-env",
        "role": args.role,
        "model_backend": args.model_backend,
        "model": config.model,
        "embedding_model": args.embedding_model,
        "embedding_dimensions": args.embedding_dimensions,
        "env_file": report.env_file,
        "env_file_exists": report.env_file_exists,
        "env_loaded": report.loaded,
        "api_key_present": report.api_key_present,
        "base_url_present": report.base_url_present,
        "model_present": bool(config.model),
        "embedding_api_key_present": report.embedding_api_key_present,
        "embedding_base_url_present": report.embedding_base_url_present,
        "embedding_model_present": report.embedding_model_present,
        "secret_values_printed": False,
    }


def _build_full_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("full", help="依次运行 main、compare、ablate 三组实验，并在同一输出根目录下生成产物。")
    parser.add_argument("--output-dir", default="artifacts/long_term_memory_graph/full")
    parser.add_argument("--case-limit", type=int, default=None)
    parser.add_argument("--case-offset", type=int, default=0)
    parser.add_argument("--shard-id", type=int, default=None)
    parser.add_argument("--num-shards", type=int, default=None)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--dataset-path", default=None)
    parser.add_argument("--resume", action="store_true", help="从现有输出根目录续跑各子实验。")
    parser.add_argument("--judge-backend", default="deterministic_probe")
    parser.add_argument("--include-official-baselines", action="store_true", help="compare/full 时把已接入的官方 baseline adapter 加入本地运行。")
    parser.add_argument("--include-proxy-extension", action="store_true", help="compare/full 时把 proxy 扩展方法加入本地运行。")
    parser.add_argument("--judge-model-backend", default=None, choices=["openai", "openai_http"])
    parser.add_argument("--judge-model", default=None, help="真实 judge 使用的模型名；也可由 OPENAI_MODEL/MODEL_NAME 提供。")
    parser.add_argument("--model-backend", default="agentorch_probe")
    parser.add_argument("--model", default=None, help="真实 API 后端使用的模型名；也可由 OPENAI_MODEL/MODEL_NAME 提供。")
    parser.add_argument("--embedding-model", default=None, help="真实 embedding 使用的模型名；也可由 OPENAI_EMBEDDING_MODEL 提供。")
    parser.add_argument("--embedding-dimensions", type=int, default=None, help="embedding 维度。")
    parser.add_argument("--env-file", default=".env", help="真实 API 后端加载的 env 文件路径；默认使用当前目录 .env。")
    parser.add_argument("--no-env-file", action="store_true", help="禁用 env 文件加载，仅使用当前进程环境变量。")
    parser.add_argument("--overwrite-env", action="store_true", help="允许 env 文件覆盖当前进程已有环境变量。")
    parser.set_defaults(handler=_run_full_from_args)


def _run_full_from_args(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.output_dir)
    common = {
        "case_limit": args.case_limit,
        "case_offset": args.case_offset,
        "shard_id": args.shard_id,
        "num_shards": args.num_shards,
        "runs": args.runs,
        "seed": args.seed,
        "dataset_path": args.dataset_path,
        "resume": args.resume,
        "judge_backend": args.judge_backend,
        "judge_model_backend": args.judge_model_backend,
        "judge_model_name": args.judge_model,
        "model_backend": args.model_backend,
        "model_name": args.model,
        "embedding_model": args.embedding_model,
        "embedding_dimensions": args.embedding_dimensions,
        "env_file": args.env_file,
        "load_env": not args.no_env_file,
        "overwrite_env": args.overwrite_env,
    }
    main_manifest = _main_runner().run_main_experiment(output_dir=root / "main", **common)
    comparison_manifest = _comparison_runner().run_comparison_experiment(
        output_dir=root / "comparison",
        include_official_baselines=args.include_official_baselines,
        include_proxy_extension=args.include_proxy_extension,
        **common,
    )
    ablation_manifest = _ablation_runner().run_ablation_experiment(output_dir=root / "ablation", **common)
    return {
        "command": "full",
        "output_dir": str(root.resolve()),
        "main": main_manifest,
        "comparison": comparison_manifest,
        "ablation": ablation_manifest,
    }


def _serialize(result: Any) -> str:
    if isinstance(result, BaseModel):
        payload: Any = result.model_dump()
    else:
        payload = result
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = args.handler(args)
    if result is not None:
        print(_serialize(result))
    return 0


__all__ = ["build_parser", "main"]
