from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from agentorch.config import initialize_environment

PROBE_MODEL_BACKENDS = {"probe"}
LIVE_MODEL_BACKENDS = {"openai", "local-llm"}
API_KEY_ENV_NAMES = ("OPENAI_API_KEY", "API_KEY", "api_key", "OPENAI_KEY", "openai_api_key")
BASE_URL_ENV_NAMES = ("OPENAI_BASE_URL", "BASE_URL", "base_url", "OPENAI_API_BASE", "openai_base_url")
MODEL_ENV_NAMES = ("OPENAI_CHAT_MODEL", "OPENAI_MODEL", "AGENTORCH_MODEL", "MODEL_NAME", "model_name", "MODEL", "model")


@dataclass(frozen=True)
class EnvLoadReport:
    env_file: str | None
    env_file_exists: bool
    loaded: bool
    model_backend: str
    api_key_present: bool
    base_url_present: bool
    model_present: bool


def is_probe_backend(model_backend: str) -> bool:
    return model_backend.strip().lower() in PROBE_MODEL_BACKENDS


def load_experiment_env(
    *,
    env_file: str | Path | None = None,
    model_backend: str,
    load_env: bool = True,
    overwrite_env: bool = False,
) -> EnvLoadReport:
    path = Path(env_file) if env_file is not None else Path.cwd() / ".env"
    exists = path.exists()
    loaded = False
    if load_env and exists:
        initialize_environment(path, overwrite=overwrite_env)
        loaded = True
    _apply_common_aliases(overwrite=overwrite_env)
    return EnvLoadReport(
        env_file=str(path),
        env_file_exists=exists,
        loaded=loaded,
        model_backend=model_backend,
        api_key_present=bool(_first_env(*API_KEY_ENV_NAMES)),
        base_url_present=bool(_first_env(*BASE_URL_ENV_NAMES)),
        model_present=bool(_first_env(*MODEL_ENV_NAMES)),
    )


def validate_live_backend_env(
    *,
    model_backend: str,
    env_file: str | Path | None = None,
    load_env: bool = True,
    overwrite_env: bool = False,
) -> EnvLoadReport:
    backend = model_backend.strip().lower()
    if backend not in LIVE_MODEL_BACKENDS:
        raise ValueError(f"Unsupported live model backend: {model_backend}. Use one of {sorted(LIVE_MODEL_BACKENDS)}.")
    report = load_experiment_env(
        env_file=env_file,
        model_backend=backend,
        load_env=load_env,
        overwrite_env=overwrite_env,
    )
    if not report.api_key_present:
        raise ValueError("真实模型运行缺少 API key。请设置 OPENAI_API_KEY，或其兼容别名 API_KEY / api_key。")
    if not report.base_url_present:
        raise ValueError("真实模型运行缺少 base_url。请设置 OPENAI_BASE_URL，或其兼容别名 BASE_URL / base_url。")
    if not report.model_present:
        raise ValueError(
            "真实模型运行缺少模型名。请设置 OPENAI_CHAT_MODEL / OPENAI_MODEL / AGENTORCH_MODEL，或传入兼容别名 MODEL_NAME。"
        )
    return report


def _apply_common_aliases(*, overwrite: bool) -> None:
    _copy_first_env("OPENAI_API_KEY", API_KEY_ENV_NAMES[1:], overwrite=overwrite)
    _copy_first_env("OPENAI_BASE_URL", BASE_URL_ENV_NAMES[1:], overwrite=overwrite)
    _copy_first_env("OPENAI_CHAT_MODEL", MODEL_ENV_NAMES[1:], overwrite=overwrite)
    _copy_first_env("OPENAI_MODEL", ("OPENAI_CHAT_MODEL",) + MODEL_ENV_NAMES[2:], overwrite=overwrite)
    _copy_first_env("AGENTORCH_MODEL", ("OPENAI_CHAT_MODEL", "OPENAI_MODEL") + MODEL_ENV_NAMES[3:], overwrite=overwrite)


def _copy_first_env(target: str, aliases: tuple[str, ...], *, overwrite: bool) -> None:
    if not overwrite and os.getenv(target):
        return
    value = _first_env(*aliases)
    if value:
        os.environ[target] = value


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


__all__ = [
    "API_KEY_ENV_NAMES",
    "BASE_URL_ENV_NAMES",
    "EnvLoadReport",
    "LIVE_MODEL_BACKENDS",
    "MODEL_ENV_NAMES",
    "is_probe_backend",
    "load_experiment_env",
    "validate_live_backend_env",
]
