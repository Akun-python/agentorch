from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_INPUT_PATH = PROJECT_ROOT / "自建ai数据集"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"
DEFAULT_SOURCE_COLUMN = "文本"
DEFAULT_LABEL_COLUMN = "领域标签"
DEFAULT_OUTPUT_COLUMN = "AI生成文本"
DEFAULT_MODEL_COLUMN = "AI生成模型"
DEFAULT_THREAD_COLUMN = "生成线程ID"
DEFAULT_STATUS_COLUMN = "生成状态"
DEFAULT_PROMPT_TOKENS_COLUMN = "提示token数"
DEFAULT_COMPLETION_TOKENS_COLUMN = "补全token数"
DEFAULT_TOTAL_TOKENS_COLUMN = "总token数"
DEFAULT_FIRST_TOKEN_LATENCY_COLUMN = "首token延迟秒"
DEFAULT_TOTAL_LATENCY_COLUMN = "总耗时秒"
DEFAULT_FINISH_REASON_COLUMN = "完成原因"

MODEL_ENV_NAMES = (
    "AI_FOR_DETECT_MODEL",
    "OPENAI_MODEL",
    "OPENAI_CHAT_MODEL",
    "AGENTORCH_MODEL",
)
MODEL_LIST_ENV_NAMES = (
    "AI_FOR_DETECT_MODELS",
    "OPENAI_MODELS",
)


def resolve_model_name(explicit_model: str | None) -> str:
    candidate = (explicit_model or "").strip()
    if candidate:
        return candidate
    for env_name in MODEL_ENV_NAMES:
        value = os.getenv(env_name)
        if value and value.strip():
            return value.strip()
    raise ValueError(
        "未配置模型名。请通过 --model 传入，或在当前 shell 中设置 "
        "AI_FOR_DETECT_MODEL / OPENAI_MODEL / OPENAI_CHAT_MODEL / AGENTORCH_MODEL。"
    )


def parse_model_list(raw_value: str | None) -> list[str]:
    if raw_value is None:
        return []
    values = [item.strip() for item in raw_value.replace("\n", ",").split(",")]
    return [item for item in values if item]


def resolve_model_names(explicit_models: str | list[str] | None) -> list[str]:
    if isinstance(explicit_models, str):
        parsed = parse_model_list(explicit_models)
        if parsed:
            return parsed
    elif explicit_models:
        cleaned = [str(item).strip() for item in explicit_models if str(item).strip()]
        if cleaned:
            return cleaned

    for env_name in MODEL_LIST_ENV_NAMES:
        parsed = parse_model_list(os.getenv(env_name))
        if parsed:
            return parsed
    return [resolve_model_name(None)]
