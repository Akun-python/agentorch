"""Model provider abstractions and built-in adapters.

The framework talks to models through a normalized adapter interface so the
runtime can remain provider-agnostic. Built-in adapters can be mixed with
custom provider registrations for non-SDK HTTP services.
"""

from .base import BaseModelAdapter
from .openai_compatible_http import OpenAICompatibleHTTPModel
from .openai_model import OpenAIModel
from .registry import create_model_adapter, list_model_providers, register_model_provider

register_model_provider("openai", OpenAIModel.from_config)
register_model_provider("openai_http", OpenAICompatibleHTTPModel.from_config)

__all__ = [
    "BaseModelAdapter",
    "OpenAICompatibleHTTPModel",
    "OpenAIModel",
    "create_model_adapter",
    "list_model_providers",
    "register_model_provider",
]
