from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from agentorch.config import ModelConfig
from agentorch.config.settings import _get_api_key, _get_base_url
from agentorch.core import Message, ModelRequest, ModelResponse, StreamChunk, ToolCall, UsageInfo
from agentorch.models.base import BaseModelAdapter


class OpenAIModel(BaseModelAdapter):
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int | None = 2048,
        timeout: float = 60.0,
        max_retries: int = 2,
        temperature: float | None = None,
    ) -> None:
        self.config = ModelConfig(
            model=model,
            api_key=api_key or _get_api_key(),
            base_url=base_url if base_url is not None else _get_base_url(),
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            temperature=temperature,
        )
        self._client = AsyncOpenAI(api_key=self.config.api_key, base_url=self.config.base_url, timeout=self.config.timeout, max_retries=0)

    async def generate(self, request: ModelRequest) -> ModelResponse:
        last_error: Exception | None = None
        for _ in range(self.config.max_retries + 1):
            try:
                raw = await self._client.chat.completions.create(**self._build_payload(request, stream=False))
                return self._normalize_response(raw)
            except Exception as exc:  # pragma: no cover
                last_error = exc
                await asyncio.sleep(0.3)
        assert last_error is not None
        raise last_error

    async def stream(self, request: ModelRequest) -> AsyncIterator[StreamChunk]:
        stream = await self._client.chat.completions.create(**self._build_payload(request, stream=True))
        async for chunk in stream:  # pragma: no cover
            delta_text = ""
            tool_calls: list[ToolCall] = []
            finish_reason = None
            if chunk.choices:
                choice = chunk.choices[0]
                finish_reason = choice.finish_reason
                if choice.delta and choice.delta.content:
                    delta_text = choice.delta.content
                if choice.delta and choice.delta.tool_calls:
                    for tool_call in choice.delta.tool_calls:
                        arguments = {}
                        if tool_call.function and tool_call.function.arguments:
                            try:
                                arguments = json.loads(tool_call.function.arguments)
                            except json.JSONDecodeError:
                                arguments = {"raw": tool_call.function.arguments}
                        tool_calls.append(
                            ToolCall(
                                id=tool_call.id or "",
                                name=(tool_call.function.name if tool_call.function else "") or "",
                                arguments=arguments,
                            )
                        )
            yield StreamChunk(delta_text=delta_text, tool_calls=tool_calls, finish_reason=finish_reason, raw=chunk)

    def _build_payload(self, request: ModelRequest, stream: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [self._message_to_openai(message) for message in request.messages],
            "stream": stream,
            "max_tokens": request.max_tokens or self.config.max_tokens,
            "temperature": request.temperature if request.temperature is not None else self.config.temperature,
        }
        if request.tools:
            payload["tools"] = request.tools
        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice
        if request.response_format is not None:
            payload["response_format"] = request.response_format
        return {key: value for key, value in payload.items() if value is not None}

    def _message_to_openai(self, message: Message) -> dict[str, Any]:
        content: str | None = message.content
        if message.role == "assistant" and message.tool_calls and not content:
            content = None
        data: dict[str, Any] = {"role": message.role, "content": content}
        if message.name:
            data["name"] = message.name
        if message.tool_call_id:
            data["tool_call_id"] = message.tool_call_id
        if message.role == "assistant" and message.tool_calls:
            data["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.name,
                        "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
                    },
                }
                for tool_call in message.tool_calls
            ]
        return data

    def _normalize_response(self, raw: Any) -> ModelResponse:
        choice = raw.choices[0]
        content = choice.message.content or ""
        tool_calls: list[ToolCall] = []
        for tool_call in choice.message.tool_calls or []:
            arguments = {}
            if tool_call.function and tool_call.function.arguments:
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {"raw": tool_call.function.arguments}
            tool_calls.append(ToolCall(id=tool_call.id, name=tool_call.function.name, arguments=arguments))
        usage = UsageInfo(
            prompt_tokens=getattr(raw.usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(raw.usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(raw.usage, "total_tokens", 0) or 0,
        )
        message = Message(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
            metadata={"tool_calls": [call.model_dump() for call in tool_calls]},
        )
        return ModelResponse(message=message, content=content, tool_calls=tool_calls, finish_reason=choice.finish_reason, usage=usage, raw=raw)
