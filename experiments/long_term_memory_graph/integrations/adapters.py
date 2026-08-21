from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from ..api.models import MemoryCapsuleCandidate, RecallRequest, RecallResponse


class LongTermMemoryAdapter(Protocol):
    """长期记忆适配器协议，用于接入不同 Agent 运行时。"""

    def build_recall_request(self, agent_state: Mapping[str, Any]) -> RecallRequest:
        raise NotImplementedError

    def build_store_candidates(self, agent_state: Mapping[str, Any]) -> list[MemoryCapsuleCandidate]:
        raise NotImplementedError

    def consume_recall_response(self, response: RecallResponse) -> Any:
        raise NotImplementedError
