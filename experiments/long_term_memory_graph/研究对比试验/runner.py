from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(project_root))
    from experiments.long_term_memory_graph.core import (
        CORE_LOCAL_BASELINE_METHODS,
        NON_OFFICIAL_PROXY_EXTENSION_METHODS,
        OFFICIAL_BASELINE_METHODS,
        ExperimentRunConfig,
        run_suite,
    )
    from experiments.long_term_memory_graph.研究对比试验.protocol import build_comparison_protocol_metadata
else:
    from ..core import (
        CORE_LOCAL_BASELINE_METHODS,
        NON_OFFICIAL_PROXY_EXTENSION_METHODS,
        OFFICIAL_BASELINE_METHODS,
        ExperimentRunConfig,
        run_suite,
    )
    from .protocol import build_comparison_protocol_metadata


def run_comparison_experiment(
    *,
    output_dir: str | Path,
    methods: tuple[str, ...] = CORE_LOCAL_BASELINE_METHODS,
    include_official_baselines: bool = False,
    include_proxy_extension: bool = False,
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
) -> dict[str, object]:
    selected_methods = _resolve_methods(
        methods,
        include_official_baselines=include_official_baselines,
        include_proxy_extension=include_proxy_extension,
    )
    result = run_suite(
        ExperimentRunConfig(
            suite="comparison",
            methods=selected_methods,
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
            protocol_metadata=build_comparison_protocol_metadata(selected_methods),
        )
    )
    return result.manifest


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "compare",
        help="运行 E2：默认跑本地核心基线；可按需加入官方 baseline 或 proxy 扩展。",
    )
    parser.add_argument("--methods", default=",".join(CORE_LOCAL_BASELINE_METHODS))
    parser.add_argument("--include-official-baselines", action="store_true", help="把已接入的官方 baseline adapter 加入本地对比运行。")
    parser.add_argument("--include-proxy-extension", action="store_true", help="显式把 proxy 扩展方法加入本地对比运行。")
    _add_common_args(parser, default_output="artifacts/long_term_memory_graph/comparison")
    parser.set_defaults(handler=run_from_args)


def run_from_args(args: argparse.Namespace) -> dict[str, object]:
    methods = tuple(item.strip() for item in args.methods.split(",") if item.strip())
    return run_comparison_experiment(
        output_dir=args.output_dir,
        methods=methods,
        include_official_baselines=args.include_official_baselines,
        include_proxy_extension=args.include_proxy_extension,
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
    )


def _add_common_args(parser: argparse.ArgumentParser, *, default_output: str) -> None:
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


def _resolve_methods(
    methods: tuple[str, ...],
    *,
    include_official_baselines: bool,
    include_proxy_extension: bool,
) -> tuple[str, ...]:
    selected = list(methods)
    if include_official_baselines:
        selected.extend(OFFICIAL_BASELINE_METHODS)
    if include_proxy_extension:
        selected.extend(NON_OFFICIAL_PROXY_EXTENSION_METHODS)
    return tuple(dict.fromkeys(selected))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="直接运行 E2 强基线对比实验。")
    parser.add_argument("--methods", default=",".join(CORE_LOCAL_BASELINE_METHODS))
    parser.add_argument("--include-official-baselines", action="store_true")
    parser.add_argument("--include-proxy-extension", action="store_true")
    _add_common_args(parser, default_output="artifacts/long_term_memory_graph/comparison")
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = run_from_args(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
