"""Plugin interfaces and the plugin manager.

Plugins are extension points for providers and backends such as models,
memory stores, policies, tools, and sandbox implementations.
"""

from .manager import Plugin, PluginManager

__all__ = ["Plugin", "PluginManager"]
