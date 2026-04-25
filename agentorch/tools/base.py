from __future__ import annotations

import asyncio
import inspect
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    risk_level: str = "low"
    timeout: float = 30.0
    retryable: bool = False
    needs_sandbox: bool = False


class ToolResult(BaseModel):
    tool_name: str
    data: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error: str | None = None
    duration: float | None = None


class ToolError(Exception):
    def __init__(self, message: str, *, tool_name: str | None = None) -> None:
        super().__init__(message)
        self.tool_name = tool_name


class BaseTool(ABC):
    spec: ToolSpec
    input_model: type[BaseModel]

    @abstractmethod
    async def run(self, input_data: BaseModel) -> ToolResult:
        raise NotImplementedError

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.spec.name,
                "description": self.spec.description,
                "parameters": self.spec.input_schema,
            },
        }

    async def aclose(self) -> None:
        return None

    def close(self) -> None:
        return None


class FunctionTool(BaseTool):
    def __init__(
        self,
        *,
        name: str,
        description: str,
        input_model: type[BaseModel],
        func: Any,
        risk_level: str = "low",
        timeout: float = 30.0,
        retryable: bool = False,
        needs_sandbox: bool = False,
        aclose_callback: Callable[[], Awaitable[None]] | None = None,
        close_callback: Callable[[], None] | None = None,
    ) -> None:
        self.input_model = input_model
        self.func = func
        self._aclose_callback = aclose_callback
        self._close_callback = close_callback
        self.spec = ToolSpec(
            name=name,
            description=description,
            input_schema=input_model.model_json_schema(),
            risk_level=risk_level,
            timeout=timeout,
            retryable=retryable,
            needs_sandbox=needs_sandbox,
        )

    async def run(self, input_data: BaseModel) -> ToolResult:
        started = time.perf_counter()
        try:
            if inspect.iscoroutinefunction(self.func):
                result = await asyncio.wait_for(self.func(input_data), timeout=self.spec.timeout)
            else:
                result = await asyncio.wait_for(asyncio.to_thread(self.func, input_data), timeout=self.spec.timeout)
            if isinstance(result, BaseModel):
                payload = result.model_dump()
            elif isinstance(result, dict):
                payload = result
            else:
                payload = {"result": result}
            return ToolResult(tool_name=self.spec.name, data=payload, duration=time.perf_counter() - started)
        except asyncio.TimeoutError as exc:
            raise ToolError(f"Tool '{self.spec.name}' timed out after {self.spec.timeout} seconds.", tool_name=self.spec.name) from exc
        except Exception as exc:
            raise ToolError(str(exc), tool_name=self.spec.name) from exc

    async def aclose(self) -> None:
        if self._aclose_callback is not None:
            await self._aclose_callback()

    def close(self) -> None:
        if self._close_callback is not None:
            self._close_callback()
