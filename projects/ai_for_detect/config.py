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

MODEL_ENV_NAMES = (
    "AI_FOR_DETECT_MODEL",
    "OPENAI_MODEL",
    "OPENAI_CHAT_MODEL",
    "AGENTORCH_MODEL",
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
