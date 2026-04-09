from __future__ import annotations

from abc import ABC, abstractmethod

from agentorch.core import Decision, ModelResponse


class BasePolicy(ABC):
    @abstractmethod
    async def decide(self, response: ModelResponse) -> Decision:
        raise NotImplementedError
