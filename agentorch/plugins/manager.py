from __future__ import annotations

from typing import Any, Protocol


class Plugin(Protocol):
    name: str

    def setup(self, manager: "PluginManager") -> None:
        ...


class PluginManager:
    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._extensions: dict[str, list[Any]] = {
            "model_provider": [],
            "tool": [],
            "memory_backend": [],
            "memory_governance": [],
            "policy": [],
            "reasoning_framework": [],
            "evolution_algorithm": [],
            "retriever": [],
            "embedding_provider": [],
            "reranker": [],
            "sandbox": [],
        }

    def register_plugin(self, plugin: Plugin) -> None:
        self._plugins[plugin.name] = plugin
        plugin.setup(self)

    def register_extension(self, kind: str, extension: Any) -> None:
        self._extensions.setdefault(kind, []).append(extension)

    def get_extensions(self, kind: str) -> list[Any]:
        return list(self._extensions.get(kind, []))
