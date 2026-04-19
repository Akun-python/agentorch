from __future__ import annotations

from .openai_compatible_http import OpenAICompatibleHTTPModel
from .openai_model import OpenAIModel
from .registry import register_model_provider

_BOOTSTRAPPED = False


def bootstrap_model_defaults(*, force: bool = False) -> None:
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED and not force:
        return
    register_model_provider("openai", OpenAIModel.from_config)
    register_model_provider("openai_http", OpenAICompatibleHTTPModel.from_config)
    _BOOTSTRAPPED = True
