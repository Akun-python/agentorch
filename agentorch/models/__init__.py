"""Model provider abstractions and built-in adapters.

The framework talks to models through a normalized adapter interface so the
runtime can remain provider-agnostic. v1 ships with an OpenAI-compatible adapter.
"""

from .base import BaseModelAdapter
from .openai_model import OpenAIModel

__all__ = ["BaseModelAdapter", "OpenAIModel"]
