from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MemoryBackend(ABC):
    kind: str = "memory_backend"


class MemoryMechanism(ABC):
    kind: str = "memory_mechanism"

    @abstractmethod
    def supports(self, operation: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def invoke(self, manager: Any, operation: str, **kwargs: Any) -> Any:
        raise NotImplementedError


class MemoryGovernance(ABC):
    @abstractmethod
    async def search_collective_memory(self, manager: Any, **kwargs: Any) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def promote_collective_memory(self, manager: Any, **kwargs: Any) -> int:
        raise NotImplementedError

    @abstractmethod
    async def validate_collective_memory(self, manager: Any, record_id: int) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    async def deprecate_collective_memory(self, manager: Any, record_id: int) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    async def collect_candidate_notes(self, manager: Any, thread_id: str, *, task_id: str | None = None):
        raise NotImplementedError


class MemoryPromotionPolicy(ABC):
    kind: str = "memory_promotion_policy"

    @abstractmethod
    async def promote(self, manager: Any, **kwargs: Any) -> list[dict[str, Any]]:
        raise NotImplementedError


class MemoryIndexPolicy(ABC):
    kind: str = "memory_index_policy"

    @abstractmethod
    def build_index(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError


class MemoryRecallPolicy(ABC):
    kind: str = "memory_recall_policy"

    @abstractmethod
    async def recall(self, manager: Any, **kwargs: Any) -> list[dict[str, Any]]:
        raise NotImplementedError


class MemoryDecayPolicy(ABC):
    kind: str = "memory_decay_policy"

    @abstractmethod
    def score(self, record: dict[str, Any], **kwargs: Any) -> tuple[float, dict[str, float]]:
        raise NotImplementedError
