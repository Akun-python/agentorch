from __future__ import annotations

import argparse
from pathlib import Path

from .config import (
    DEFAULT_INPUT_PATH,
    DEFAULT_LABEL_COLUMN,
    DEFAULT_OUTPUT_COLUMN,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SOURCE_COLUMN,
)
from .env_loader import load_project_env
from .generator import AgentTorchSentenceGenerator, MultiModelSentenceGenerator
from .pipeline import AIDetectBatchPipeline, PipelineConfig


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="用 AgentTorch 批量改写中文句子。")
    parser.add_argument("--input-path", type=Path, default=DEFAULT_INPUT_PATH, help="输入目录或单个 xlsx 文件路径。")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="输出目录。")
    parser.add_argument("--model", type=str, default=None, help="模型名；未传时从当前 shell 环境变量读取。")
    parser.add_argument("--models", type=str, default=None, help="多个模型名，逗号分隔；同一 Excel 内按行交叉使用。")
    parser.add_argument("--source-column", type=str, default=DEFAULT_SOURCE_COLUMN, help="原始文本列名。")
    parser.add_argument("--label-column", type=str, default=DEFAULT_LABEL_COLUMN, help="领域标签列名。")
    parser.add_argument("--output-column", type=str, default=DEFAULT_OUTPUT_COLUMN, help="输出文本列名。")
    parser.add_argument("--max-rows", type=int, default=None, help="每个文件最多处理多少行，便于先做小样验证。")
    parser.add_argument("--flush-every", type=int, default=20, help="每生成多少条就落盘一次。")
    parser.add_argument("--temperature", type=float, default=0.8, help="生成温度。")
    parser.add_argument("--max-tokens", type=int, default=256, help="单条输出的最大 token 数。")
    parser.add_argument("--min-request-interval", type=float, default=0.0, help="两次请求之间的最小间隔秒数。")
    parser.add_argument("--timeout", type=float, default=60.0, help="单次请求超时秒数。")
    parser.add_argument("--max-retries", type=int, default=2, help="接口失败后的最大重试次数。")
    parser.add_argument("--overwrite", action="store_true", help="忽略已有输出文件，重新生成。")
    return parser


def main() -> None:
    loaded_env_path = load_project_env()
    if loaded_env_path is not None:
        print(f"已加载环境变量文件：{loaded_env_path}")
    args = build_arg_parser().parse_args()
    if args.models:
        generator = MultiModelSentenceGenerator(
            model_names=args.models,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            min_request_interval=args.min_request_interval,
            timeout=args.timeout,
            max_retries=args.max_retries,
        )
    else:
        generator = AgentTorchSentenceGenerator(
            model_name=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            min_request_interval=args.min_request_interval,
            timeout=args.timeout,
            max_retries=args.max_retries,
        )
    try:
        config = PipelineConfig(
            input_path=args.input_path,
            output_dir=args.output_dir,
            source_column=args.source_column,
            label_column=args.label_column,
            output_column=args.output_column,
            flush_every=args.flush_every,
            max_rows=args.max_rows,
            overwrite=args.overwrite,
        )
        pipeline = AIDetectBatchPipeline(generator=generator, config=config)
        summaries = pipeline.run()
    finally:
        generator.close()

    total_generated = sum(item.generated_rows for item in summaries)
    total_skipped = sum(item.skipped_rows for item in summaries)
    total_failed = sum(item.failed_rows for item in summaries)
    total_rows = sum(item.total_rows for item in summaries)
    total_prompt_tokens = sum(item.prompt_tokens for item in summaries)
    total_completion_tokens = sum(item.completion_tokens for item in summaries)
    total_tokens = sum(item.total_tokens for item in summaries)
    latency_denominator = max(total_generated, 1)
    average_first_token_latency = sum(
        item.average_first_token_latency_seconds * item.generated_rows for item in summaries
    ) / latency_denominator
    average_total_latency = sum(
        item.average_total_latency_seconds * item.generated_rows for item in summaries
    ) / latency_denominator
    print(
        f"全部完成：目标 {total_rows} 条，新增 {total_generated} 条，"
        f"跳过 {total_skipped} 条，失败 {total_failed} 条。"
    )
    print(
        f"Token统计：提示 {total_prompt_tokens}，补全 {total_completion_tokens}，总计 {total_tokens}；"
        f"平均首token延迟 {average_first_token_latency:.3f} 秒，平均总耗时 {average_total_latency:.3f} 秒。"
    )
    if pipeline.combined_dataset_csv_path is not None:
        print(f"汇总数据集：{pipeline.combined_dataset_csv_path.resolve()}")
    print(f"输出目录：{args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
