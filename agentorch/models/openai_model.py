from __future__ import annotations

import asyncio
import base64
import datetime as dt
import inspect
import json
import mimetypes
import random
from collections.abc import AsyncIterator
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, ClassVar

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError

from agentorch.config import ModelConfig
from agentorch.config.settings import _get_api_key, _get_base_url
from agentorch.core import Message, ModelRequest, ModelResponse, StreamChunk, ToolCall, UsageInfo
from agentorch.models.base import BaseModelAdapter


class OpenAIModel(BaseModelAdapter):
    _throttle_locks: ClassVar[dict[str, asyncio.Lock]] = {}
    _next_request_times: ClassVar[dict[str, float]] = {}

    def __init__(
        self,
        model: str,
        vision_model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int | None = 2048,
        timeout: float = 60.0,
        max_retries: int = 2,
        retry_base_delay: float = 2.0,
        retry_max_delay: float = 30.0,
        retry_jitter: float = 0.25,
        min_request_interval: float = 0.0,
        temperature: float | None = None,
    ) -> None:
        self.config = ModelConfig(
            model=model,
            vision_model=vision_model,
            api_key=api_key or _get_api_key(),
            base_url=base_url if base_url is not None else _get_base_url(),
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            retry_base_delay=retry_base_delay,
            retry_max_delay=retry_max_delay,
            retry_jitter=retry_jitter,
            min_request_interval=min_request_interval,
            temperature=temperature,
        )
        self._client = AsyncOpenAI(api_key=self.config.api_key, base_url=self.config.base_url, timeout=self.config.timeout, max_retries=0)

    @classmethod
    def from_config(cls, config: ModelConfig | dict[str, Any] | str | None = None, **overrides: Any) -> "OpenAIModel":
        resolved = ModelConfig.from_any(config, **overrides)
        return cls(
            model=resolved.model,
            vision_model=resolved.vision_model,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
            max_tokens=resolved.max_tokens,
            timeout=resolved.timeout,
            max_retries=resolved.max_retries,
            retry_base_delay=resolved.retry_base_delay,
            retry_max_delay=resolved.retry_max_delay,
            retry_jitter=resolved.retry_jitter,
            min_request_interval=resolved.min_request_interval,
            temperature=resolved.temperature,
        )

    async def analyze_image(
        self,
        *,
        prompt: str,
        image_path: str | Path | None = None,
        image_url: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> ModelResponse:
        request = ModelRequest(
            messages=[
                Message(
                    role="user",
                    content="",
                    metadata={
                        "multimodal_content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": self._resolve_image_url(image_path=image_path, image_url=image_url)}},
                        ]
                    },
                )
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            metadata={"model_override": model or self.config.vision_model or self.config.model, "request_kind": "image_understanding"},
        )
        return await self.generate(request)

    async def generate(self, request: ModelRequest) -> ModelResponse:
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                await self._wait_for_rate_limit_slot()
                raw = await self._client.chat.completions.create(**self._build_payload(request, stream=False))
                return self._normalize_response(raw)
            except Exception as exc:  # pragma: no cover
                last_error = exc
                if attempt >= self.config.max_retries or not self._is_retryable(exc):
                    break
                delay = self._retry_delay(exc, attempt)
                self._extend_cooldown(delay)
                await asyncio.sleep(delay)
        assert last_error is not None
        raise last_error

    async def stream(self, request: ModelRequest) -> AsyncIterator[StreamChunk]:
        last_error: Exception | None = None
        stream = None
        for attempt in range(self.config.max_retries + 1):
            try:
                await self._wait_for_rate_limit_slot()
                stream = await self._client.chat.completions.create(**self._build_payload(request, stream=True))
                break
            except Exception as exc:  # pragma: no cover
                last_error = exc
                if attempt >= self.config.max_retries or not self._is_retryable(exc):
                    break
                delay = self._retry_delay(exc, attempt)
                self._extend_cooldown(delay)
                await asyncio.sleep(delay)
        if stream is None:
            assert last_error is not None
            raise last_error
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
                        tool_name = (tool_call.function.name if tool_call.function else "") or ""
                        if tool_call.function and tool_call.function.arguments:
                            try:
                                parsed_arguments = json.loads(tool_call.function.arguments)
                                arguments = parsed_arguments if isinstance(parsed_arguments, dict) else {"raw": parsed_arguments}
                            except json.JSONDecodeError:
                                arguments = {"raw": tool_call.function.arguments}
                        if not tool_name:
                            # Some OpenAI-compatible gateways stream partial tool-call chunks
                            # where the function name is omitted until a later delta.
                            # Skip those incomplete fragments here; Runtime._model_round()
                            # will merge later chunks that carry the actual name.
                            continue
                        tool_calls.append(
                            ToolCall(
                                id=tool_call.id or "",
                                name=tool_name,
                                arguments=arguments,
                            )
                        )
            yield StreamChunk(delta_text=delta_text, tool_calls=tool_calls, finish_reason=finish_reason, raw=chunk)

    def _build_payload(self, request: ModelRequest, stream: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.metadata.get("model_override") or self.config.model,
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
        multimodal_content = message.metadata.get("multimodal_content")
        content: str | list[dict[str, Any]] | None = multimodal_content if multimodal_content is not None else message.content
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

    def _resolve_image_url(self, *, image_path: str | Path | None, image_url: str | None) -> str:
        if image_url:
            return image_url
        if image_path is None:
            raise ValueError("image_path and image_url cannot both be empty.")
        resolved = Path(image_path).expanduser()
        if not resolved.is_absolute():
            resolved = Path.cwd() / resolved
        if not resolved.exists():
            raise FileNotFoundError(f"Image file not found: {resolved}")
        mime_type, _ = mimetypes.guess_type(resolved.name)
        mime_type = mime_type or "application/octet-stream"
        encoded = base64.b64encode(resolved.read_bytes()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _normalize_response(self, raw: Any) -> ModelResponse:
        choice = raw.choices[0]
        content = choice.message.content or ""
        tool_calls: list[ToolCall] = []
        for tool_call in choice.message.tool_calls or []:
            arguments = {}
            if tool_call.function and tool_call.function.arguments:
                try:
                    parsed_arguments = json.loads(tool_call.function.arguments)
                    arguments = parsed_arguments if isinstance(parsed_arguments, dict) else {"raw": parsed_arguments}
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

    def _retry_delay(self, exc: Exception, attempt: int) -> float:
        retry_after = self._extract_retry_after(exc)
        if retry_after is not None:
            return min(retry_after + self._jitter_value(), self.config.retry_max_delay)
        if isinstance(exc, (RateLimitError, APITimeoutError, APIConnectionError)):
            base = min(self.config.retry_base_delay * (2**attempt), self.config.retry_max_delay)
            return min(base + self._jitter_value(), self.config.retry_max_delay)
        return min(0.5 * (attempt + 1), 2.0)

    def _is_retryable(self, exc: Exception) -> bool:
        return isinstance(exc, (RateLimitError, APITimeoutError, APIConnectionError))

    def _throttle_key(self) -> str:
        return f"{self.config.base_url or 'default'}::{self.config.model}"

    async def _wait_for_rate_limit_slot(self) -> None:
        interval = max(float(self.config.min_request_interval), 0.0)
        key = self._throttle_key()
        lock = self._throttle_locks.setdefault(key, asyncio.Lock())
        loop = asyncio.get_running_loop()
        async with lock:
            now = loop.time()
            ready_at = self._next_request_times.get(key, 0.0)
            wait_time = max(ready_at - now, 0.0)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            observed = loop.time()
            next_time = observed + interval
            self._next_request_times[key] = max(self._next_request_times.get(key, 0.0), next_time)

    def _extend_cooldown(self, delay: float) -> None:
        key = self._throttle_key()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # pragma: no cover
            return
        ready_at = loop.time() + max(delay, 0.0)
        self._next_request_times[key] = max(self._next_request_times.get(key, 0.0), ready_at)

    def _jitter_value(self) -> float:
        if self.config.retry_jitter <= 0:
            return 0.0
        return random.uniform(0.0, self.config.retry_jitter)

    def _extract_retry_after(self, exc: Exception) -> float | None:
        if not isinstance(exc, RateLimitError):
            return None
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None)
        if headers:
            parsed = self._parse_retry_after_value(headers.get("retry-after"))
            if parsed is not None:
                return parsed
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            candidates = [
                body.get("retry_after"),
                body.get("retryAfter"),
                (body.get("error") or {}).get("retry_after") if isinstance(body.get("error"), dict) else None,
                (body.get("error") or {}).get("retryAfter") if isinstance(body.get("error"), dict) else None,
            ]
            for candidate in candidates:
                parsed = self._parse_retry_after_value(candidate)
                if parsed is not None:
                    return parsed
        return None

    def _parse_retry_after_value(self, value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return max(float(value), 0.0)
        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None
        try:
            return max(float(text), 0.0)
        except ValueError:
            try:
                target = parsedate_to_datetime(text)
            except (TypeError, ValueError, IndexError):
                return None
            now = dt.datetime.now(target.tzinfo or dt.timezone.utc)
            return max((target - now).total_seconds(), 0.0)

    async def aclose(self) -> None:
        close_fn = getattr(self._client, "close", None) or getattr(self._client, "aclose", None)
        if callable(close_fn):
            outcome = close_fn()
            if inspect.isawaitable(outcome):
                await outcome
