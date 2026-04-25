from __future__ import annotations

from typing import Any


MOCK_FORMAL_MODELS = ["mock:strong", "mock:balanced", "mock:weak"]

# Real-model defaults assume an OpenAI-compatible gateway that routes by model name.
# These names can be overridden from CLI when the upstream provider uses different aliases.
REFERENCE_FORMAL_MODEL = "gpt-4o"
CHEAP_FORMAL_MODELS = [
    "gpt-4o-mini",
    "deepseek-chat",
    "qwen-plus",
]
REAL_FORMAL_MODELS = [
    *CHEAP_FORMAL_MODELS,
    REFERENCE_FORMAL_MODEL,
]

REAL_ABLATION_MODELS = [
    "deepseek-chat",
    "qwen-plus",
    "gpt-4o-mini",
    REFERENCE_FORMAL_MODEL,
]

REAL_SCALING_MODEL = "gpt-4o-mini"


REAL_MODEL_RUNTIME_PROFILES: dict[str, dict[str, Any]] = {
    "deepseek-chat": {
        "timeout": 120.0,
        "max_tokens": 1024,
        "max_retries": 0,
        "retry_base_delay": 4.0,
        "retry_max_delay": 20.0,
        "min_request_interval": 1.5,
    },
    "qwen-plus": {
        "timeout": 120.0,
        "max_retries": 1,
        "retry_base_delay": 3.0,
        "retry_max_delay": 15.0,
        "min_request_interval": 0.4,
    },
    "gpt-4o-mini": {
        "timeout": 90.0,
        "max_retries": 1,
        "retry_base_delay": 2.0,
        "retry_max_delay": 12.0,
        "min_request_interval": 0.1,
    },
    "gpt-4o": {
        "timeout": 90.0,
        "max_retries": 1,
        "retry_base_delay": 2.0,
        "retry_max_delay": 12.0,
        "min_request_interval": 0.1,
    },
}


def resolve_model_runtime_profile(model_name: str) -> dict[str, Any]:
    lowered = model_name.lower()
    for key, profile in REAL_MODEL_RUNTIME_PROFILES.items():
        if key in lowered:
            return dict(profile)
    return {}
