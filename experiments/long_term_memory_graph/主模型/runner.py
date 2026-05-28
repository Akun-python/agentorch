from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    # 允许直接执行本文件，也允许作为包模块导入。
    project_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(project_root))
    from experiments.long_term_memory_graph.core import MAIN_METHOD, ExperimentRunConfig, run_suite
else:
    from ..core import MAIN_METHOD, ExperimentRunConfig, run_suite


def run_main_experiment(
    *,
    output_dir: str | Path,
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
    summary_backend: str = "template",
    summary_model_backend: str | None = None,
    summary_model: str | None = None,
    summary_max_tokens: int = 768,
    env_file: str | Path | None = ".env",
    load_env: bool = True,
    overwrite_env: bool = False,
) -> dict[str, object]:
    """运行 E1/E3/E5 主模型实验。"""

    result = run_suite(
        ExperimentRunConfig(
            suite="main",
            methods=(MAIN_METHOD,),
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
            summary_backend=summary_backend,
            summary_model_backend=summary_model_backend,
            summary_model=summary_model,
            summary_max_tokens=summary_max_tokens,
            env_file=Path(env_file) if env_file else None,
            load_env=load_env,
            overwrite_env=overwrite_env,
        )
    )
    return result.manifest


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """注册 main 子命令。"""

    parser = subparsers.add_parser(
        "main",
        help="运行 E1/E3/E5：完整克拉克星鸦长时记忆图谱主模型实验。",
    )
    _add_common_args(parser, default_output="artifacts/long_term_memory_graph/main")
    parser.set_defaults(handler=run_from_args)


def run_from_args(args: argparse.Namespace) -> dict[str, object]:
    """把 argparse 参数转成主实验函数调用。"""

    return run_main_experiment(
        output_dir=args.output_dir,
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
        summary_backend=args.summary_backend,
        summary_model_backend=args.summary_model_backend,
        summary_model=args.summary_model,
        summary_max_tokens=args.summary_max_tokens,
        env_file=args.env_file,
        load_env=not args.no_env_file,
        overwrite_env=args.overwrite_env,
    )


def _add_common_args(parser: argparse.ArgumentParser, *, default_output: str) -> None:
    """主模型实验的通用 CLI 参数。"""

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
    parser.add_argument("--summary-backend", default="template", choices=["template", "llm"], help="召回摘要器类型。")
    parser.add_argument("--summary-model-backend", default=None, choices=["openai", "openai_http"], help="LLM 摘要器的模型后端。")
    parser.add_argument("--summary-model", default=None, help="LLM 摘要器的模型名，建议使用 flash 模型。")
    parser.add_argument("--summary-max-tokens", type=int, default=768, help="LLM 摘要器输出上限。")
    parser.add_argument("--env-file", default=".env", help="真实 API 后端加载的 env 文件路径；默认使用当前目录 .env。")
    parser.add_argument("--no-env-file", action="store_true", help="禁用 env 文件加载，仅使用当前进程环境变量。")
    parser.add_argument("--overwrite-env", action="store_true", help="允许 env 文件覆盖当前进程已有环境变量。")


def main(argv: Sequence[str] | None = None) -> int:
    """支持 `python runner.py` 直接运行。"""

    parser = argparse.ArgumentParser(description="直接运行 E1/E3/E5 主模型实验。")
    _add_common_args(parser, default_output="artifacts/long_term_memory_graph/main")
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = run_from_args(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
