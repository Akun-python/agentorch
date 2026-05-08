from __future__ import annotations

import asyncio
import datetime as dt
import inspect
import json
import random
from collections.abc import AsyncIterator
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urljoin

import httpx
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError

from agentorch.config import ModelConfig
from agentorch.config.settings import DEFAULT_EMBEDDING_ENDPOINT_PATH
from agentorch.core import Message, ModelRequest, ModelResponse, StreamChunk, ToolCall, UsageInfo
from agentorch.models.embedding import EmbeddingCapableModelAdapter
from agentorch.models.media import (
    ImageGenerationCapableModelAdapter,
    ImageGenerationResult,
    RetryableImageGenerationError,
    VideoAnalysisCapableModelAdapter,
    build_candidate_image_models,
    build_data_url_from_file,
    build_image_generation_endpoint,
    build_image_generation_payload,
    decode_inline_image_bytes,
    ensure_image_generation_success,
    extract_inline_image_payload,
    resolve_image_output_path,
    resolve_video_reference,
)
from agentorch.models.speech import (
    DEFAULT_SPEECH_ENDPOINT_PATH,
    SpeechCapableModelAdapter,
    SpeechSynthesisResult,
    format_http_error_response,
    looks_like_audio_content,
    normalize_speech_speed,
    resolve_speech_output_path,
    validate_speech_response_format,
)


def _set_if_not_none(target: dict[str, Any], /, **values: Any) -> None:
    for key, value in values.items():
        if value is not None:
            target[key] = value


class OpenAIModel(
    SpeechCapableModelAdapter,
    EmbeddingCapableModelAdapter,
    ImageGenerationCapableModelAdapter,
    VideoAnalysisCapableModelAdapter,
):
    _throttle_locks: ClassVar[dict[str, asyncio.Lock]] = {}
    _next_request_times: ClassVar[dict[str, float]] = {}

    def __init__(
        self,
        model: str | None = None,
        vision_model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        auth_scheme: str = "Bearer",
        headers: dict[str, str] | None = None,
        embedding_api_key: str | None = None,
        embedding_base_url: str | None = None,
        embedding_endpoint_path: str = DEFAULT_EMBEDDING_ENDPOINT_PATH,
        embedding_model: str | None = None,
        embedding_dimensions: int | None = None,
        speech_api_key: str | None = None,
        speech_base_url: str | None = None,
        speech_endpoint_path: str = DEFAULT_SPEECH_ENDPOINT_PATH,
        speech_model: str | None = None,
        speech_voice: str | None = None,
        speech_format: str | None = None,
        speech_speed: float | None = None,
        image_api_key: str | None = None,
        image_base_url: str | None = None,
        image_explicit_url: str | None = None,
        image_model: str | None = None,
        image_aspect_ratio: str | None = None,
        image_size: str | None = None,
        image_timeout: float | None = None,
        image_fallback_models: list[str] | None = None,
        image_retry_without_proxy: bool | None = None,
        image_disable_env_proxy: bool | None = None,
        video_api_key: str | None = None,
        video_base_url: str | None = None,
        video_model: str | None = None,
        video_disable_env_proxy: bool | None = None,
        max_tokens: int | None = 2048,
        timeout: float = 60.0,
        max_retries: int = 2,
        retry_base_delay: float = 2.0,
        retry_max_delay: float = 30.0,
        retry_jitter: float = 0.25,
        min_request_interval: float = 0.0,
        temperature: float | None = None,
    ) -> None:
        config_data: dict[str, Any] = {
            "auth_scheme": auth_scheme,
            "headers": dict(headers or {}),
            "embedding_endpoint_path": embedding_endpoint_path,
            "speech_endpoint_path": speech_endpoint_path,
            "max_tokens": max_tokens,
            "timeout": timeout,
            "max_retries": max_retries,
            "retry_base_delay": retry_base_delay,
            "retry_max_delay": retry_max_delay,
            "retry_jitter": retry_jitter,
            "min_request_interval": min_request_interval,
            "temperature": temperature,
        }
        _set_if_not_none(
            config_data,
            model=model,
            vision_model=vision_model,
            api_key=api_key,
            base_url=base_url,
            embedding_api_key=embedding_api_key,
            embedding_base_url=embedding_base_url,
            embedding_model=embedding_model,
            embedding_dimensions=embedding_dimensions,
            speech_api_key=speech_api_key,
            speech_base_url=speech_base_url,
            speech_model=speech_model,
            speech_voice=speech_voice,
            speech_format=speech_format,
            speech_speed=speech_speed,
            image_api_key=image_api_key,
            image_base_url=image_base_url,
            image_explicit_url=image_explicit_url,
            image_model=image_model,
            image_aspect_ratio=image_aspect_ratio,
            image_size=image_size,
            image_timeout=image_timeout,
            image_retry_without_proxy=image_retry_without_proxy,
            image_disable_env_proxy=image_disable_env_proxy,
            video_api_key=video_api_key,
            video_base_url=video_base_url,
            video_model=video_model,
            video_disable_env_proxy=video_disable_env_proxy,
        )
        if image_fallback_models is not None:
            config_data["image_fallback_models"] = list(image_fallback_models)
        self.config = ModelConfig(**config_data)
        self._speech_http_client: httpx.AsyncClient | None = None
        self._image_http_clients: dict[bool, Any] = {}
        self._client: Any | None = None
        self._embedding_client: Any | None = None
        self._video_client: Any | None = None
        self._video_http_client: httpx.AsyncClient | None = None

    @classmethod
    def from_config(cls, config: ModelConfig | dict[str, Any] | str | None = None, **overrides: Any) -> "OpenAIModel":
        resolved = ModelConfig.from_any(config, **overrides)
        return cls(
            model=resolved.model,
            vision_model=resolved.vision_model,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
            auth_scheme=resolved.auth_scheme,
            headers=resolved.headers,
            embedding_api_key=resolved.embedding_api_key,
            embedding_base_url=resolved.embedding_base_url,
            embedding_endpoint_path=resolved.embedding_endpoint_path,
            embedding_model=resolved.embedding_model,
            embedding_dimensions=resolved.embedding_dimensions,
            speech_api_key=resolved.speech_api_key,
            speech_base_url=resolved.speech_base_url,
            speech_endpoint_path=resolved.speech_endpoint_path,
            speech_model=resolved.speech_model,
            speech_voice=resolved.speech_voice,
            speech_format=resolved.speech_format,
            speech_speed=resolved.speech_speed,
            image_api_key=resolved.image_api_key,
            image_base_url=resolved.image_base_url,
            image_explicit_url=resolved.image_explicit_url,
            image_model=resolved.image_model,
            image_aspect_ratio=resolved.image_aspect_ratio,
            image_size=resolved.image_size,
            image_timeout=resolved.image_timeout,
            image_fallback_models=resolved.image_fallback_models,
            image_retry_without_proxy=resolved.image_retry_without_proxy,
            image_disable_env_proxy=resolved.image_disable_env_proxy,
            video_api_key=resolved.video_api_key,
            video_base_url=resolved.video_base_url,
            video_model=resolved.video_model,
            video_disable_env_proxy=resolved.video_disable_env_proxy,
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

    async def embed(
        self,
        texts: list[str],
        *,
        embedding_model: str | None = None,
        dimensions: int | None = None,
    ) -> list[list[float]]:
        if not texts:
            return []
        selected_model = ((embedding_model or self.config.embedding_model) or "").strip()
        if not selected_model:
            raise ValueError("Embedding model is not configured. Set `embedding_model` or `OPENAI_EMBEDDING_MODEL`.")
        embedding_api_key = (self._embedding_api_key() or "").strip()
        embedding_base_url = (self._embedding_base_url() or "").strip()
        if not embedding_api_key:
            raise ValueError(
                "Embedding API key is not configured. Set `embedding_api_key`, `OPENAI_EMBEDDING_API_KEY`, or `OPENAI_API_KEY`."
            )
        if not embedding_base_url:
            raise ValueError(
                "Embedding base URL is not configured. Set `embedding_base_url`, `OPENAI_EMBEDDING_BASE_URL`, or `OPENAI_BASE_URL`."
            )
        selected_dimensions = dimensions if dimensions is not None else self.config.embedding_dimensions
        payload: dict[str, Any] = {"input": texts, "model": selected_model}
        if selected_dimensions is not None:
            payload["dimensions"] = int(selected_dimensions)
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                await self._wait_for_rate_limit_slot(base_url=embedding_base_url, model=selected_model)
                raw = await self._embeddings().create(**payload)
                return self._normalize_embeddings_response(raw, expected_count=len(texts))
            except Exception as exc:  # pragma: no cover
                last_error = exc
                if attempt >= self.config.max_retries or not self._is_retryable(exc):
                    break
                delay = self._retry_delay(exc, attempt)
                self._extend_cooldown(delay, base_url=embedding_base_url, model=selected_model)
                await asyncio.sleep(delay)
        assert last_error is not None
        raise last_error

    async def analyze_video(
        self,
        *,
        prompt: str,
        video_path: str | Path | None = None,
        video_url: str | None = None,
        mime_type: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> ModelResponse:
        if not prompt or not prompt.strip():
            raise ValueError("Video analysis prompt cannot be empty.")
        selected_model = ((model or self.config.video_model or self.config.vision_model or self.config.model) or "").strip()
        api_key = (self.config.video_api_key or self.config.api_key or "").strip()
        base_url = (self.config.video_base_url or self.config.base_url or "").strip()
        if not selected_model:
            raise ValueError("Video model is not configured. Set `video_model`, `vision_model`, or `model`.")
        if not api_key:
            raise ValueError("Video API key is not configured. Set `video_api_key`, `OPENAI_VIDEO_API_KEY`, or `OPENAI_API_KEY`.")
        if not base_url:
            raise ValueError("Video base URL is not configured. Set `video_base_url`, `OPENAI_VIDEO_BASE_URL`, or `OPENAI_BASE_URL`.")

        resolved_video_url, resolved_mime_type, _ = resolve_video_reference(
            video_path=video_path,
            video_url=video_url,
            mime_type=mime_type,
        )
        request = ModelRequest(
            messages=[
                Message(
                    role="user",
                    content="",
                    metadata={
                        "multimodal_content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": resolved_video_url},
                                "mime_type": resolved_mime_type,
                            },
                        ]
                    },
                )
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            metadata={"model_override": selected_model, "request_kind": "video_understanding"},
        )
        raw = await self._get_video_chat_completions().create(**self._build_payload(request, stream=False))
        return self._normalize_response(raw)

    async def generate_image(
        self,
        prompt: str,
        *,
        aspect_ratio: str | None = None,
        image_size: str | None = None,
        image_model: str | None = None,
        output_path: str | Path | None = None,
    ) -> ImageGenerationResult:
        if not prompt or not prompt.strip():
            raise ValueError("Image generation prompt cannot be empty.")

        selected_model = (image_model or self.config.image_model or "").strip()
        selected_aspect_ratio = (aspect_ratio or self.config.image_aspect_ratio or "").strip()
        selected_image_size = (image_size or self.config.image_size or "").strip()
        api_key = (self.config.image_api_key or self.config.api_key or "").strip()
        base_url = (self.config.image_base_url or "").strip()
        explicit_url = (self.config.image_explicit_url or "").strip() or None
        if not api_key:
            raise ValueError("Image API key is not configured. Set `image_api_key`, `OPENAI_IMAGE_API_KEY`, or `OPENAI_API_KEY`.")
        if not selected_model:
            raise ValueError("Image generation model is not configured. Set `image_model` or `OPENAI_IMAGE_MODEL`.")
        if not base_url and not explicit_url:
            raise ValueError(
                "Image base URL is not configured. Set `image_base_url`, `image_explicit_url`, `OPENAI_IMAGE_BASE_URL`, or `OPENAI_IMAGE_EXPLICIT_URL`."
            )

        payload = build_image_generation_payload(
            prompt.strip(),
            aspect_ratio=selected_aspect_ratio or self.config.image_aspect_ratio,
            image_size=selected_image_size or self.config.image_size,
        )
        headers = self._build_image_headers(api_key)
        candidate_models = build_candidate_image_models(selected_model, self.config.image_fallback_models)
        trust_env = not self.config.image_disable_env_proxy
        errors: list[str] = []

        for candidate in candidate_models:
            try:
                data = await self._request_image_generation_once(
                    model=candidate,
                    payload=payload,
                    headers=headers,
                    base_url=base_url,
                    explicit_url=explicit_url,
                    trust_env=trust_env,
                )
                return self._finalize_image_generation_result(
                    data=data,
                    model=candidate,
                    proxy_mode="disabled" if not trust_env else "env",
                    output_path=output_path,
                )
            except httpx.ProxyError as exc:
                errors.append(f"{candidate}: {exc}")
                if trust_env and self.config.image_retry_without_proxy:
                    try:
                        data = await self._request_image_generation_once(
                            model=candidate,
                            payload=payload,
                            headers=headers,
                            base_url=base_url,
                            explicit_url=explicit_url,
                            trust_env=False,
                        )
                        return self._finalize_image_generation_result(
                            data=data,
                            model=candidate,
                            proxy_mode="disabled-after-proxy-error",
                            output_path=output_path,
                        )
                    except Exception as retry_exc:  # noqa: BLE001
                        errors.append(f"{candidate} (retry without proxy): {retry_exc}")
                break
            except RetryableImageGenerationError as exc:
                errors.append(str(exc))
                continue

        if errors:
            tips = [
                "1. Configure `image_model` or `OPENAI_IMAGE_MODEL`.",
                "2. If a local proxy is causing issues, try `OPENAI_IMAGE_DISABLE_ENV_PROXY=1`.",
                "3. If your provider supports fallbacks, set `OPENAI_IMAGE_FALLBACK_MODELS`.",
            ]
            raise RuntimeError("Image generation failed:\n" + "\n".join(errors) + "\n\nTry:\n" + "\n".join(tips))
        raise RuntimeError("Image generation failed without a usable response.")

    async def synthesize_speech(
        self,
        text: str,
        *,
        voice: str | None = None,
        response_format: str | None = None,
        speed: float | int | str | None = None,
        speech_model: str | None = None,
        output_path: str | Path | None = None,
    ) -> SpeechSynthesisResult:
        if not text or not text.strip():
            raise ValueError("Speech input text cannot be empty.")

        selected_model = ((speech_model or self.config.speech_model) or "").strip()
        selected_voice = ((voice or self.config.speech_voice) or "").strip()
        selected_format = validate_speech_response_format(response_format or self.config.speech_format)
        selected_speed = normalize_speech_speed(speed if speed is not None else self.config.speech_speed)
        api_key = (self.config.speech_api_key or self.config.api_key or "").strip()
        base_url = (self.config.speech_base_url or self.config.base_url or "").strip()
        if not selected_model:
            raise ValueError("Speech model is not configured. Set `speech_model` or `OPENAI_TTS_MODEL`.")
        if not selected_voice:
            raise ValueError("Speech voice is not configured. Set `speech_voice` or `OPENAI_TTS_VOICE`.")
        if not api_key:
            raise ValueError("Speech API key is not configured. Set `speech_api_key`, `OPENAI_TTS_API_KEY`, or `OPENAI_API_KEY`.")
        if not base_url:
            raise ValueError("Speech base URL is not configured. Set `speech_base_url`, `OPENAI_TTS_BASE_URL`, or `OPENAI_BASE_URL`.")

        payload = {
            "model": selected_model,
            "input": text,
            "voice": selected_voice,
            "speed": selected_speed,
            "response_format": selected_format,
        }
        target = resolve_speech_output_path(output_path=output_path, response_format=selected_format)
        target.parent.mkdir(parents=True, exist_ok=True)

        response = await self._get_speech_http_client().post(
            urljoin(base_url.rstrip("/") + "/", self.config.speech_endpoint_path.lstrip("/")),
            headers=self._build_http_headers(api_key),
            json=payload,
        )
        if not response.is_success:
            raise RuntimeError(
                f"Speech synthesis request failed: HTTP {response.status_code}\n{format_http_error_response(response)}"
            )

        content_type = response.headers.get("Content-Type", "")
        if not looks_like_audio_content(content_type, response.content):
            raise RuntimeError(f"Speech synthesis response is not audio.\n{format_http_error_response(response)}")

        target.write_bytes(response.content)
        return SpeechSynthesisResult(
            output_path=str(target),
            response_format=selected_format,
            content_type=content_type or "application/octet-stream",
            bytes_written=len(response.content),
            voice=selected_voice,
            speed=selected_speed,
            model=selected_model,
        )

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self._require_chat_configuration(model_override=self._request_model_override(request))
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                await self._wait_for_rate_limit_slot()
                raw = await self._chat_completions().create(**self._build_payload(request, stream=False))
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
        self._require_chat_configuration(model_override=self._request_model_override(request))
        last_error: Exception | None = None
        stream = None
        for attempt in range(self.config.max_retries + 1):
            try:
                await self._wait_for_rate_limit_slot()
                stream = await self._chat_completions().create(**self._build_payload(request, stream=True))
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
        partial_tool_calls: dict[str, dict[str, Any]] = {}
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
                    for position, tool_call in enumerate(choice.delta.tool_calls):
                        keys = self._stream_tool_call_keys(tool_call, position=position)
                        state = None
                        for key in keys:
                            existing = partial_tool_calls.get(key)
                            if existing is not None:
                                state = existing
                                break
                        if state is None:
                            state = {
                                "id": "",
                                "name": "",
                                "arguments_text": "",
                            }
                        for key in keys:
                            partial_tool_calls[key] = state
                        if tool_call.id:
                            state["id"] = tool_call.id
                        fragment_name = (tool_call.function.name if tool_call.function else "") or ""
                        if fragment_name:
                            state["name"] = self._merge_stream_tool_name(state["name"], fragment_name)
                        fragment_arguments = (tool_call.function.arguments if tool_call.function else "") or ""
                        if fragment_arguments:
                            state["arguments_text"] += fragment_arguments
                        tool_name = state["name"]
                        if not tool_name:
                            continue
                        arguments = self._parse_stream_tool_arguments(state["arguments_text"])
                        tool_calls.append(
                            ToolCall(
                                id=state["id"] or keys[0],
                                name=tool_name,
                                arguments=arguments,
                            )
                        )
            yield StreamChunk(delta_text=delta_text, tool_calls=tool_calls, finish_reason=finish_reason, raw=chunk)

    def _build_payload(self, request: ModelRequest, stream: bool) -> dict[str, Any]:
        selected_model = self._resolve_chat_model(self._request_model_override(request))
        payload: dict[str, Any] = {
            "model": selected_model,
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
        data_url, _, _ = build_data_url_from_file(image_path, default_mime_type="application/octet-stream")
        return data_url

    def _normalize_response(self, raw: Any) -> ModelResponse:
        choice = raw.choices[0]
        content = choice.message.content or ""
        tool_calls: list[ToolCall] = []
        for tool_call in getattr(choice.message, "tool_calls", None) or []:
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

    def _stream_tool_call_keys(self, tool_call: Any, *, position: int) -> list[str]:
        keys: list[str] = []
        if getattr(tool_call, "index", None) is not None:
            keys.append(f"index:{tool_call.index}")
        if getattr(tool_call, "id", None):
            keys.append(str(tool_call.id))
        if not keys:
            keys.append(f"position:{position}")
        return keys

    def _merge_stream_tool_name(self, current: str, fragment: str) -> str:
        if not current:
            return fragment
        if fragment == current:
            return current
        if fragment.startswith(current):
            return fragment
        if current.startswith(fragment):
            return current
        return current + fragment

    def _parse_stream_tool_arguments(self, text: str) -> dict[str, Any]:
        if not text.strip():
            return {}
        try:
            parsed_arguments = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return parsed_arguments if isinstance(parsed_arguments, dict) else {"raw": parsed_arguments}

    def _build_http_headers(self, api_key: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self.config.headers}
        if api_key:
            token = api_key if not self.config.auth_scheme else f"{self.config.auth_scheme} {api_key}"
            headers.setdefault("Authorization", token)
        return headers

    def _get_client(self):
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                max_retries=0,
            )
        return self._client

    def _chat_completions(self):
        return self._get_client().chat.completions

    def _embedding_api_key(self) -> str | None:
        return self.config.embedding_api_key or self.config.api_key

    def _embedding_base_url(self) -> str | None:
        return self.config.embedding_base_url or self.config.base_url

    def _embeddings(self):
        embedding_api_key = self._embedding_api_key()
        embedding_base_url = self._embedding_base_url()
        if embedding_api_key == self.config.api_key and embedding_base_url == self.config.base_url:
            return self._get_client().embeddings
        if self._embedding_client is None:
            self._embedding_client = AsyncOpenAI(
                api_key=embedding_api_key,
                base_url=embedding_base_url,
                timeout=self.config.timeout,
                max_retries=0,
            )
        return self._embedding_client.embeddings

    def _get_video_chat_completions(self):
        if self._video_client is None:
            self._video_http_client = httpx.AsyncClient(timeout=self.config.timeout, trust_env=not self.config.video_disable_env_proxy)
            self._video_client = AsyncOpenAI(
                api_key=self.config.video_api_key or self.config.api_key,
                base_url=self.config.video_base_url or self.config.base_url,
                timeout=self.config.timeout,
                max_retries=0,
                http_client=self._video_http_client,
                default_headers=dict(self.config.headers),
            )
        return self._video_client.chat.completions

    def _get_speech_http_client(self) -> httpx.AsyncClient:
        if self._speech_http_client is None:
            self._speech_http_client = httpx.AsyncClient(timeout=self.config.timeout)
        return self._speech_http_client

    def _get_image_http_client(self, *, trust_env: bool):
        client = self._image_http_clients.get(trust_env)
        if client is None:
            client = httpx.AsyncClient(timeout=self.config.image_timeout, trust_env=trust_env)
            self._image_http_clients[trust_env] = client
        return client

    def _build_image_headers(self, api_key: str) -> dict[str, str]:
        headers = self._build_http_headers(api_key)
        headers.setdefault("x-goog-api-key", api_key)
        return headers

    async def _request_image_generation_once(
        self,
        *,
        model: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        base_url: str,
        explicit_url: str | None,
        trust_env: bool,
    ) -> dict[str, Any]:
        endpoint = build_image_generation_endpoint(base_url, model, explicit_url)
        try:
            response = await self._get_image_http_client(trust_env=trust_env).post(
                endpoint,
                headers=headers,
                json=payload,
            )
        except httpx.ProxyError:
            raise
        except httpx.TimeoutException as exc:
            raise RetryableImageGenerationError(
                f"Image generation request timed out. model={model}, timeout_seconds={self.config.image_timeout}"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"Image generation request failed before a response was returned. model={model}, error={exc}") from exc
        return ensure_image_generation_success(model, response)

    def _finalize_image_generation_result(
        self,
        *,
        data: dict[str, Any],
        model: str,
        proxy_mode: str,
        output_path: str | Path | None,
    ) -> ImageGenerationResult:
        encoded, mime_type = extract_inline_image_payload(data)
        target = resolve_image_output_path(output_path=output_path, mime_type=mime_type)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = decode_inline_image_bytes(encoded)
        target.write_bytes(payload)
        return ImageGenerationResult(
            output_path=str(target),
            mime_type=mime_type,
            bytes_written=len(payload),
            model=model,
            proxy_mode=proxy_mode,
        )

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

    def _throttle_key(self, *, base_url: str | None = None, model: str | None = None) -> str:
        return f"{base_url or self.config.base_url or 'default'}::{model or self.config.model}"

    def _request_model_override(self, request: ModelRequest) -> str | None:
        override = request.metadata.get("model_override")
        return override if isinstance(override, str) else None

    def _resolve_chat_model(self, model_override: str | None = None) -> str:
        selected_model = ((model_override or self.config.model) or "").strip()
        if not selected_model:
            raise ValueError("Chat model is not configured. Pass `model=...` or set it on `ModelConfig`.")
        return selected_model

    def _require_chat_configuration(self, *, model_override: str | None = None) -> None:
        self._resolve_chat_model(model_override)
        api_key = (self.config.api_key or "").strip()
        base_url = (self.config.base_url or "").strip()
        if not api_key:
            raise ValueError("Chat API key is not configured. Set `api_key` or `OPENAI_API_KEY`.")
        if not base_url:
            raise ValueError("Chat base URL is not configured. Set `base_url` or `OPENAI_BASE_URL`.")

    async def _wait_for_rate_limit_slot(self, *, base_url: str | None = None, model: str | None = None) -> None:
        interval = max(float(self.config.min_request_interval), 0.0)
        key = self._throttle_key(base_url=base_url, model=model)
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

    def _extend_cooldown(self, delay: float, *, base_url: str | None = None, model: str | None = None) -> None:
        key = self._throttle_key(base_url=base_url, model=model)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # pragma: no cover
            return
        ready_at = loop.time() + max(delay, 0.0)
        self._next_request_times[key] = max(self._next_request_times.get(key, 0.0), ready_at)

    def _normalize_embeddings_response(self, raw: Any, *, expected_count: int | None = None) -> list[list[float]]:
        data = getattr(raw, "data", None)
        if not isinstance(data, list) or not data:
            raise RuntimeError("Embedding response did not contain data.")
        ordered: list[list[float] | None] = [None] * max(expected_count or 0, len(data))
        extras: list[list[float]] = []
        for position, item in enumerate(data):
            embedding = getattr(item, "embedding", None)
            if embedding is None:
                raise RuntimeError("Embedding response item did not contain an embedding.")
            vector = [float(value) for value in embedding]
            index = getattr(item, "index", None)
            if isinstance(index, int) and 0 <= index < len(ordered) and ordered[index] is None:
                ordered[index] = vector
                continue
            if position < len(ordered) and ordered[position] is None:
                ordered[position] = vector
                continue
            extras.append(vector)
        normalized = [item for item in ordered if item is not None]
        normalized.extend(extras)
        if not normalized:
            raise RuntimeError("Embedding response did not contain any usable vectors.")
        return normalized

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
        if self._client is not None:
            close_fn = getattr(self._client, "close", None) or getattr(self._client, "aclose", None)
            if callable(close_fn):
                outcome = close_fn()
                if inspect.isawaitable(outcome):
                    await outcome
            self._client = None
        if self._embedding_client is not None:
            close_fn = getattr(self._embedding_client, "close", None) or getattr(self._embedding_client, "aclose", None)
            if callable(close_fn):
                outcome = close_fn()
                if inspect.isawaitable(outcome):
                    await outcome
            self._embedding_client = None
        if self._speech_http_client is not None:
            await self._speech_http_client.aclose()
            self._speech_http_client = None
        for client in self._image_http_clients.values():
            close_async = getattr(client, "aclose", None)
            if callable(close_async):
                await close_async()
        self._image_http_clients.clear()
        if self._video_client is not None:
            close_fn = getattr(self._video_client, "close", None) or getattr(self._video_client, "aclose", None)
            if callable(close_fn):
                outcome = close_fn()
                if inspect.isawaitable(outcome):
                    await outcome
            self._video_client = None
        if self._video_http_client is not None:
            await self._video_http_client.aclose()
            self._video_http_client = None
