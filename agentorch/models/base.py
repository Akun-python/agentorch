from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from agentorch.core import ModelRequest, ModelResponse, StreamChunk


class BaseModelAdapter(ABC):
    @abstractmethod
    async def generate(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError

    async def stream(self, request: ModelRequest) -> AsyncIterator[StreamChunk]:
        response = await self.generate(request)
        yield StreamChunk(delta_text=response.content, tool_calls=response.tool_calls, finish_reason=response.finish_reason)

    async def aclose(self) -> None:
        return None

    def close(self) -> None:
        return None
