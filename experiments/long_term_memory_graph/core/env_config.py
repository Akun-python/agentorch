from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from agentorch.config import ModelConfig, initialize_environment

# 允许离线探针与真实 OpenAI-compatible 后端共用同一套 CLI 参数。
PROBE_MODEL_BACKENDS = {"agentorch_probe", "deterministic_probe", "probe"}
LIVE_MODEL_BACKENDS = {"openai", "openai_http"}
API_KEY_ENV_NAMES = ("OPENAI_API_KEY", "API_KEY", "api_key", "OPENAI_KEY", "openai_api_key")
BASE_URL_ENV_NAMES = ("OPENAI_BASE_URL", "BASE_URL", "base_url", "OPENAI_API_BASE", "openai_base_url")
MODEL_ENV_NAMES = ("OPENAI_MODEL", "OPENAI_CHAT_MODEL", "AGENTORCH_MODEL", "MODEL_NAME", "model_name", "MODEL", "model")
EMBEDDING_API_KEY_ENV_NAMES = ("OPENAI_EMBEDDING_API_KEY", "OPENAI_API_KEY", "API_KEY", "api_key")
EMBEDDING_BASE_URL_ENV_NAMES = ("OPENAI_EMBEDDING_BASE_URL", "OPENAI_BASE_URL", "BASE_URL", "base_url")
EMBEDDING_MODEL_ENV_NAMES = ("OPENAI_EMBEDDING_MODEL", "OPENAI_EMBEDDING_MODEL_NAME", "EMBEDDING_MODEL", "MODEL_NAME", "model_name")


@dataclass(frozen=True)
class EnvLoadReport:
    """环境变量加载结果，只记录是否存在，不记录密钥内容。"""

    env_file: str | None
    env_file_exists: bool
    loaded: bool
    model_backend: str
    api_key_present: bool
    base_url_present: bool
    model_present: bool
    embedding_api_key_present: bool
    embedding_base_url_present: bool
    embedding_model_present: bool


def is_probe_backend(model_backend: str) -> bool:
    """判断是否使用离线探针后端。"""

    return model_backend.strip().lower() in PROBE_MODEL_BACKENDS


def load_experiment_env(
    *,
    env_file: str | Path | None,
    model_backend: str,
    load_env: bool,
    role_prefix: str | None = None,
    overwrite_env: bool = False,
) -> EnvLoadReport:
    """加载实验环境并规范化常见变量别名。"""

    path = Path(env_file) if env_file is not None else None
    exists = bool(path and path.exists())
    loaded = False
    if load_env and path is not None and exists:
        initialize_environment(path, overwrite=overwrite_env)
        loaded = True
    _apply_common_aliases(overwrite=overwrite_env, role_prefix=role_prefix)
    return EnvLoadReport(
        env_file=str(path) if path is not None else None,
        env_file_exists=exists,
        loaded=loaded,
        model_backend=model_backend,
        api_key_present=bool(_role_first_env(role_prefix, *API_KEY_ENV_NAMES)),
        base_url_present=bool(_role_first_env(role_prefix, *BASE_URL_ENV_NAMES)),
        model_present=bool(_role_first_env(role_prefix, *MODEL_ENV_NAMES)),
        embedding_api_key_present=bool(_role_first_env(role_prefix, *EMBEDDING_API_KEY_ENV_NAMES)),
        embedding_base_url_present=bool(_role_first_env(role_prefix, *EMBEDDING_BASE_URL_ENV_NAMES)),
        embedding_model_present=bool(_role_first_env(role_prefix, *EMBEDDING_MODEL_ENV_NAMES)),
    )


def build_live_model_config(
    *,
    model_backend: str,
    model_name: str | None,
    env_file: str | Path | None,
    load_env: bool,
    role_prefix: str | None = None,
    overwrite_env: bool = False,
) -> tuple[ModelConfig, EnvLoadReport]:
    """根据 CLI 参数和环境变量构造真实模型配置。"""

    backend = model_backend.strip().lower()
    if backend not in LIVE_MODEL_BACKENDS:
        raise ValueError(f"Unsupported live model backend: {model_backend}. Use one of {sorted(LIVE_MODEL_BACKENDS)}.")
    report = load_experiment_env(
        env_file=env_file,
        model_backend=backend,
        load_env=load_env,
        role_prefix=role_prefix,
        overwrite_env=overwrite_env,
    )
    resolved_model = model_name or _role_first_env(role_prefix, *MODEL_ENV_NAMES)
    if not resolved_model:
        raise ValueError(
            "Live AgentTorch model requires --model or OPENAI_MODEL/OPENAI_CHAT_MODEL/AGENTORCH_MODEL/MODEL_NAME in the environment."
        )
    resolved_api_key = _role_first_env(role_prefix, *API_KEY_ENV_NAMES)
    resolved_base_url = _role_first_env(role_prefix, *BASE_URL_ENV_NAMES)
    config = ModelConfig(provider=backend, model=resolved_model, api_key=resolved_api_key, base_url=resolved_base_url)
    if not config.api_key:
        raise ValueError("Live AgentTorch model requires OPENAI_API_KEY, API_KEY, or api_key.")
    if not config.base_url:
        raise ValueError("Live AgentTorch model requires OPENAI_BASE_URL, BASE_URL, or base_url.")
    return config, report


def resolve_embedding_env(*, role_prefix: str | None = None) -> dict[str, str | None]:
    """解析 embedding 相关环境变量。"""

    return {
        "embedding_api_key": _role_first_env(role_prefix, *EMBEDDING_API_KEY_ENV_NAMES),
        "embedding_base_url": _role_first_env(role_prefix, *EMBEDDING_BASE_URL_ENV_NAMES),
        "embedding_model": _role_first_env(role_prefix, *EMBEDDING_MODEL_ENV_NAMES),
    }


def _apply_common_aliases(*, overwrite: bool, role_prefix: str | None = None) -> None:
    """把 API_KEY/BASE_URL/MODEL_NAME 等别名补成 AgentTorch 默认名。"""

    _copy_first_env("OPENAI_API_KEY", API_KEY_ENV_NAMES[1:], overwrite=overwrite)
    _copy_first_env("OPENAI_BASE_URL", BASE_URL_ENV_NAMES[1:], overwrite=overwrite)
    _copy_first_env("OPENAI_MODEL", MODEL_ENV_NAMES[1:], overwrite=overwrite)
    if not role_prefix:
        return
    prefix = role_prefix.strip().upper()
    _copy_first_env(f"{prefix}_OPENAI_API_KEY", tuple(f"{prefix}_{name}" for name in API_KEY_ENV_NAMES[1:]), overwrite=overwrite)
    _copy_first_env(f"{prefix}_OPENAI_BASE_URL", tuple(f"{prefix}_{name}" for name in BASE_URL_ENV_NAMES[1:]), overwrite=overwrite)
    _copy_first_env(f"{prefix}_OPENAI_MODEL", tuple(f"{prefix}_{name}" for name in MODEL_ENV_NAMES[1:]), overwrite=overwrite)


def _copy_first_env(target: str, aliases: tuple[str, ...], *, overwrite: bool) -> None:
    """把第一个可用别名复制到目标环境变量。"""

    if not overwrite and os.getenv(target):
        return
    value = _first_env(*aliases)
    if value:
        os.environ[target] = value


def _first_env(*names: str) -> str | None:
    """返回第一个非空环境变量值。"""

    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def _role_first_env(role_prefix: str | None, *names: str) -> str | None:
    """优先读取带角色前缀的变量，例如 JUDGE_OPENAI_MODEL。"""

    if role_prefix:
        prefix = role_prefix.strip().upper()
        value = _first_env(*(f"{prefix}_{name}" for name in names))
        if value:
            return value
    return _first_env(*names)


__all__ = [
    "API_KEY_ENV_NAMES",
    "BASE_URL_ENV_NAMES",
    "EMBEDDING_API_KEY_ENV_NAMES",
    "EMBEDDING_BASE_URL_ENV_NAMES",
    "EMBEDDING_MODEL_ENV_NAMES",
    "EnvLoadReport",
    "LIVE_MODEL_BACKENDS",
    "MODEL_ENV_NAMES",
    "PROBE_MODEL_BACKENDS",
    "build_live_model_config",
    "is_probe_backend",
    "load_experiment_env",
    "resolve_embedding_env",
]
