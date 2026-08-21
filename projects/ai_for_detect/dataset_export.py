from __future__ import annotations

from pathlib import Path

import pandas as pd


DATASET_COLUMNS = [
    "样本ID",
    "来源文件",
    "原始行号",
    "领域标签",
    "原始人类文本",
    "AI文本",
    "AI生成模型",
    "生成线程ID",
    "生成状态",
    "提示token数",
    "补全token数",
    "总token数",
    "首token延迟秒",
    "总耗时秒",
    "完成原因",
]


def build_dataset_frame(
    *,
    work_df: pd.DataFrame,
    source_path: Path,
    source_column: str,
    label_column: str,
    output_column: str,
    model_column: str,
    thread_column: str,
    status_column: str,
    prompt_tokens_column: str,
    completion_tokens_column: str,
    total_tokens_column: str,
    first_token_latency_column: str,
    total_latency_column: str,
    finish_reason_column: str,
) -> pd.DataFrame:
    row_count = len(work_df)
    source_stem = source_path.stem
    frame = pd.DataFrame(
        {
            "样本ID": [f"{source_stem}-{row_index + 1:06d}" for row_index in range(row_count)],
            "来源文件": [source_path.name] * row_count,
            "原始行号": list(range(1, row_count + 1)),
            "领域标签": _string_series(work_df, label_column),
            "原始人类文本": _string_series(work_df, source_column),
            "AI文本": _string_series(work_df, output_column),
            "AI生成模型": _string_series(work_df, model_column),
            "生成线程ID": _string_series(work_df, thread_column),
            "生成状态": _string_series(work_df, status_column),
            "提示token数": _nullable_numeric_series(work_df, prompt_tokens_column),
            "补全token数": _nullable_numeric_series(work_df, completion_tokens_column),
            "总token数": _nullable_numeric_series(work_df, total_tokens_column),
            "首token延迟秒": _nullable_numeric_series(work_df, first_token_latency_column),
            "总耗时秒": _nullable_numeric_series(work_df, total_latency_column),
            "完成原因": _string_series(work_df, finish_reason_column),
        }
    )
    return frame[DATASET_COLUMNS]


def dataset_csv_path(*, output_dir: Path, source_path: Path) -> Path:
    return output_dir / f"{source_path.stem}_数据集.csv"


def combined_dataset_csv_path(*, output_dir: Path) -> Path:
    return output_dir / "ai_for_detect_数据集.csv"


def save_dataset_csv(*, dataset_df: pd.DataFrame, output_path: Path) -> None:
    dataset_df.to_csv(output_path, index=False, encoding="utf-8-sig")


def merge_dataset_frames(dataset_frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not dataset_frames:
        return pd.DataFrame(columns=DATASET_COLUMNS)
    merged = pd.concat(dataset_frames, ignore_index=True)
    return merged[DATASET_COLUMNS]


def _string_series(frame: pd.DataFrame, column_name: str) -> pd.Series:
    if column_name not in frame.columns:
        return pd.Series([""] * len(frame), dtype="string")
    return frame[column_name].fillna("").astype("string")


def _nullable_numeric_series(frame: pd.DataFrame, column_name: str) -> pd.Series:
    if column_name not in frame.columns:
        return pd.Series([pd.NA] * len(frame), dtype="Float64")
    return pd.to_numeric(frame[column_name], errors="coerce").astype("Float64")
