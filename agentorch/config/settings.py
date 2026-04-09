from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, Field


def _load_local_env() -> None:
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def _normalize_openai_base_url(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().rstrip("/")
    if cleaned.endswith("/chat/completions"):
        return cleaned[: -len("/chat/completions")]
    parsed = urlparse(cleaned)
    if parsed.scheme and parsed.netloc:
        return cleaned
    return None


def _get_api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")


def _get_base_url() -> str | None:
    return _normalize_openai_base_url(os.getenv("OPENAI_BASE_URL") or os.getenv("BASE_URL"))


_load_local_env()


class ModelConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    api_key: str | None = Field(default_factory=_get_api_key)
    base_url: str | None = Field(default_factory=_get_base_url)
    max_tokens: int | None = 2048
    timeout: float = 60.0
    max_retries: int = 2
    temperature: float | None = None


class MemoryConfig(BaseModel):
    checkpoint_path: Path = Path(".agentorch/checkpoints.db")
    record_path: Path = Path(".agentorch/records.db")
    message_window: int = 12
    summary_window: int = 40


class SandboxConfig(BaseModel):
    enabled: bool = True
    default_timeout: float = 30.0
    allowed_paths: list[Path] = Field(default_factory=lambda: [Path.cwd()])
    command_allowlist: list[str] = Field(default_factory=list)
    command_blocklist: list[str] = Field(default_factory=list)


class RuntimeConfig(BaseModel):
    system_prompt: str = (
        "You are a capable and careful agent. Use tools when they improve accuracy, "
        "stay concise, and return structured results when requested."
    )
    max_steps: int = 8
    auto_select_skills: bool = True
    parser_retry_limit: int = 1
    enable_retrieval: bool = False
    max_retrieved_chunks: int = 5
