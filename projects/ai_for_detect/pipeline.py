from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import (
    DEFAULT_COMPLETION_TOKENS_COLUMN,
    DEFAULT_FINISH_REASON_COLUMN,
    DEFAULT_FIRST_TOKEN_LATENCY_COLUMN,
    DEFAULT_INPUT_PATH,
    DEFAULT_LABEL_COLUMN,
    DEFAULT_MODEL_COLUMN,
    DEFAULT_OUTPUT_COLUMN,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PROMPT_TOKENS_COLUMN,
    DEFAULT_SOURCE_COLUMN,
    DEFAULT_STATUS_COLUMN,
    DEFAULT_THREAD_COLUMN,
    DEFAULT_TOTAL_LATENCY_COLUMN,
    DEFAULT_TOTAL_TOKENS_COLUMN,
)
from .generator import SentenceGenerator
from .metrics import RewriteMetrics, RewriteResult


@dataclass(slots=True)
class PipelineConfig:
    input_path: Path = DEFAULT_INPUT_PATH
    output_dir: Path = DEFAULT_OUTPUT_DIR
    source_column: str = DEFAULT_SOURCE_COLUMN
    label_column: str = DEFAULT_LABEL_COLUMN
    output_column: str = DEFAULT_OUTPUT_COLUMN
    model_column: str = DEFAULT_MODEL_COLUMN
    thread_column: str = DEFAULT_THREAD_COLUMN
    status_column: str = DEFAULT_STATUS_COLUMN
    prompt_tokens_column: str = DEFAULT_PROMPT_TOKENS_COLUMN
    completion_tokens_column: str = DEFAULT_COMPLETION_TOKENS_COLUMN
    total_tokens_column: str = DEFAULT_TOTAL_TOKENS_COLUMN
    first_token_latency_column: str = DEFAULT_FIRST_TOKEN_LATENCY_COLUMN
    total_latency_column: str = DEFAULT_TOTAL_LATENCY_COLUMN
    finish_reason_column: str = DEFAULT_FINISH_REASON_COLUMN
    flush_every: int = 20
    max_rows: int | None = None
    overwrite: bool = False
    file_glob: str = "*.xlsx"


@dataclass(slots=True)
class FileRunSummary:
    input_path: Path
    output_path: Path
    total_rows: int
    generated_rows: int
    skipped_rows: int
    failed_rows: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    average_first_token_latency_seconds: float = 0.0
    average_total_latency_seconds: float = 0.0


class AIDetectBatchPipeline:
    """逐文件读取 Excel，并生成对应的 AI 文本。"""

    def __init__(self, *, generator: SentenceGenerator, config: PipelineConfig) -> None:
        self.generator = generator
        self.config = config

    def run(self) -> list[FileRunSummary]:
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        summaries: list[FileRunSummary] = []
        for source_path in self._iter_input_files():
            summaries.append(self._run_single_file(source_path))
        return summaries

    def _iter_input_files(self) -> list[Path]:
        input_path = self.config.input_path
        if input_path.is_file():
            return [input_path]
        if not input_path.exists():
            raise FileNotFoundError(f"输入路径不存在：{input_path}")
        return sorted(path for path in input_path.glob(self.config.file_glob) if path.is_file())

    def _run_single_file(self, source_path: Path) -> FileRunSummary:
        source_df = pd.read_excel(source_path)
        self._validate_columns(source_df, source_path)
        output_path = self.config.output_dir / f"{source_path.stem}_ai生成.xlsx"
        work_df = self._prepare_work_dataframe(source_df=source_df, output_path=output_path)

        limit = min(len(work_df), self.config.max_rows) if self.config.max_rows is not None else len(work_df)
        generated_rows = 0
        skipped_rows = 0
        failed_rows = 0
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        first_token_latency_sum = 0.0
        total_latency_sum = 0.0

        for row_index in range(limit):
            existing_value = str(work_df.at[row_index, self.config.output_column]).strip()
            if existing_value:
                skipped_rows += 1
                continue

            source_text = str(work_df.at[row_index, self.config.source_column]).strip()
            domain_value = work_df.at[row_index, self.config.label_column] if self.config.label_column in work_df.columns else None
            domain_label = None if pd.isna(domain_value) else str(domain_value).strip()
            thread_id = self._build_thread_id(source_path=source_path, row_index=row_index)
            model_name = self._resolve_model_name_for_row(row_index=row_index)

            try:
                rewrite_result = self._rewrite_row(
                    source_text=source_text,
                    domain_label=domain_label,
                    thread_id=thread_id,
                    row_index=row_index,
                )
                work_df.at[row_index, self.config.output_column] = rewrite_result.text
                work_df.at[row_index, self.config.model_column] = model_name
                work_df.at[row_index, self.config.thread_column] = thread_id
                work_df.at[row_index, self.config.status_column] = "success"
                self._write_metrics(work_df=work_df, row_index=row_index, metrics=rewrite_result.metrics)
                generated_rows += 1
                prompt_tokens += rewrite_result.metrics.prompt_tokens
                completion_tokens += rewrite_result.metrics.completion_tokens
                total_tokens += rewrite_result.metrics.total_tokens
                first_token_latency_sum += rewrite_result.metrics.first_token_latency_seconds
                total_latency_sum += rewrite_result.metrics.total_latency_seconds
            except Exception as exc:  # pragma: no cover - 真实接口错误保留到运行期
                work_df.at[row_index, self.config.status_column] = f"error: {exc}"
                failed_rows += 1

            processed_rows = generated_rows + failed_rows
            if processed_rows and processed_rows % max(self.config.flush_every, 1) == 0:
                self._save_output(work_df, output_path)
                print(f"[{source_path.name}] 已生成 {generated_rows} 条，失败 {failed_rows} 条。")

        self._save_output(work_df, output_path)
        average_first_token_latency_seconds = first_token_latency_sum / generated_rows if generated_rows else 0.0
        average_total_latency_seconds = total_latency_sum / generated_rows if generated_rows else 0.0
        print(
            f"[{source_path.name}] 完成，目标 {limit} 条，新增 {generated_rows} 条，"
            f"跳过 {skipped_rows} 条，失败 {failed_rows} 条，"
            f"总token {total_tokens}，平均首token延迟 {average_first_token_latency_seconds:.3f} 秒。"
        )
        return FileRunSummary(
            input_path=source_path,
            output_path=output_path,
            total_rows=limit,
            generated_rows=generated_rows,
            skipped_rows=skipped_rows,
            failed_rows=failed_rows,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            average_first_token_latency_seconds=average_first_token_latency_seconds,
            average_total_latency_seconds=average_total_latency_seconds,
        )

    def _validate_columns(self, source_df: pd.DataFrame, source_path: Path) -> None:
        if self.config.source_column not in source_df.columns:
            raise KeyError(f"{source_path.name} 缺少文本列：{self.config.source_column}")
        if self.config.label_column not in source_df.columns:
            raise KeyError(f"{source_path.name} 缺少标签列：{self.config.label_column}")

    def _prepare_work_dataframe(self, *, source_df: pd.DataFrame, output_path: Path) -> pd.DataFrame:
        if output_path.exists() and not self.config.overwrite:
            work_df = pd.read_excel(output_path)
            if len(work_df) != len(source_df):
                work_df = source_df.copy()
            else:
                for column in source_df.columns:
                    if column not in work_df.columns:
                        work_df[column] = source_df[column]
        else:
            work_df = source_df.copy()

        for column_name in (
            self.config.output_column,
            self.config.model_column,
            self.config.thread_column,
            self.config.status_column,
            self.config.finish_reason_column,
        ):
            if column_name not in work_df.columns:
                work_df[column_name] = ""
            work_df[column_name] = work_df[column_name].fillna("").astype(str)

        for column_name in (
            self.config.prompt_tokens_column,
            self.config.completion_tokens_column,
            self.config.total_tokens_column,
        ):
            if column_name not in work_df.columns:
                work_df[column_name] = pd.Series([pd.NA] * len(work_df), dtype="Int64")
            else:
                work_df[column_name] = pd.to_numeric(work_df[column_name], errors="coerce").astype("Int64")

        for column_name in (
            self.config.first_token_latency_column,
            self.config.total_latency_column,
        ):
            if column_name not in work_df.columns:
                work_df[column_name] = pd.Series([pd.NA] * len(work_df), dtype="Float64")
            else:
                work_df[column_name] = pd.to_numeric(work_df[column_name], errors="coerce").astype("Float64")
        return work_df

    def _save_output(self, dataframe: pd.DataFrame, output_path: Path) -> None:
        dataframe.to_excel(output_path, index=False)

    def _build_thread_id(self, *, source_path: Path, row_index: int) -> str:
        digest = hashlib.md5(source_path.stem.encode("utf-8")).hexdigest()[:10]
        return f"ai-for-detect-{digest}-{row_index:06d}"

    def _resolve_model_name_for_row(self, *, row_index: int) -> str:
        resolver = getattr(self.generator, "resolve_model_for_row", None)
        if callable(resolver):
            return str(resolver(row_index=row_index))
        return str(getattr(self.generator, "model_name", ""))

    def _rewrite_row(self, *, source_text: str, domain_label: str | None, thread_id: str, row_index: int) -> RewriteResult:
        rewrite_record = getattr(self.generator, "rewrite_record", None)
        if callable(rewrite_record):
            return rewrite_record(
                source_text=source_text,
                domain_label=domain_label,
                thread_id=thread_id,
                row_index=row_index,
            )
        text = self.generator.rewrite_text(
            source_text=source_text,
            domain_label=domain_label,
            thread_id=thread_id,
            row_index=row_index,
        )
        return RewriteResult(
            text=text,
            model_name=self._resolve_model_name_for_row(row_index=row_index),
            metrics=RewriteMetrics(),
        )

    def _write_metrics(self, *, work_df: pd.DataFrame, row_index: int, metrics: RewriteMetrics) -> None:
        work_df.at[row_index, self.config.prompt_tokens_column] = metrics.prompt_tokens
        work_df.at[row_index, self.config.completion_tokens_column] = metrics.completion_tokens
        work_df.at[row_index, self.config.total_tokens_column] = metrics.total_tokens
        work_df.at[row_index, self.config.first_token_latency_column] = round(metrics.first_token_latency_seconds, 6)
        work_df.at[row_index, self.config.total_latency_column] = round(metrics.total_latency_seconds, 6)
        work_df.at[row_index, self.config.finish_reason_column] = metrics.finish_reason
