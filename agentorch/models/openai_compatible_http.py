from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from urllib.parse import urljoin

import httpx

from agentorch.config import ModelConfig
from agentorch.config.settings import DEFAULT_EMBEDDING_ENDPOINT_PATH
from agentorch.models.speech import DEFAULT_SPEECH_ENDPOINT_PATH

from .openai_model import OpenAIModel, _set_if_not_none


def _namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(**{key: _namespace(item) for key, item in value.items()})
    if isinstance(value, list):
        return [_namespace(item) for item in value]
    return value


class _HTTPStreamingResponse:
    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self._lines = response.aiter_lines()

    def __aiter__(self):
        return self

    async def __anext__(self):
        async for line in self._lines:
            text = line.strip()
            if not text.startswith("data:"):
                continue
            payload = text[5:].strip()
            if payload == "[DONE]":
                break
            if not payload:
                continue
            return _namespace(json.loads(payload))
        await self._response.aclose()
        raise StopAsyncIteration


class _HTTPChatCompletions:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
        endpoint_path: str,
        api_key: str | None,
        auth_scheme: str,
        extra_headers: dict[str, str],
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/") + "/"
        self._endpoint_path = endpoint_path.lstrip("/")
        self._api_key = api_key
        self._auth_scheme = auth_scheme
        self._extra_headers = dict(extra_headers)

    async def create(self, **kwargs):
        url = urljoin(self._base_url, self._endpoint_path)
        headers = {"Content-Type": "application/json", **self._extra_headers}
        if self._api_key:
            token = self._api_key if not self._auth_scheme else f"{self._auth_scheme} {self._api_key}"
            headers.setdefault("Authorization", token)
        request = self._client.build_request("POST", url, headers=headers, json=kwargs)
        response = await self._client.send(request, stream=bool(kwargs.get("stream")))
        response.raise_for_status()
        if kwargs.get("stream"):
            return _HTTPStreamingResponse(response)
        return _namespace(response.json())


class _HTTPEmbeddings:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
        endpoint_path: str,
        api_key: str | None,
        auth_scheme: str,
        extra_headers: dict[str, str],
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/") + "/"
        self._endpoint_path = endpoint_path.lstrip("/")
        self._api_key = api_key
        self._auth_scheme = auth_scheme
        self._extra_headers = dict(extra_headers)

    async def create(self, **kwargs):
        url = urljoin(self._base_url, self._endpoint_path)
        headers = {"Content-Type": "application/json", **self._extra_headers}
        if self._api_key:
            token = self._api_key if not self._auth_scheme else f"{self._auth_scheme} {self._api_key}"
            headers.setdefault("Authorization", token)
        request = self._client.build_request("POST", url, headers=headers, json=kwargs)
        response = await self._client.send(request)
        response.raise_for_status()
        return _namespace(response.json())


class OpenAICompatibleHTTPModel(OpenAIModel):
    def __init__(
        self,
        model: str | None = None,
        vision_model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        endpoint_path: str = "/chat/completions",
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
        client: httpx.AsyncClient | None = None,
    ) -> None:
        config_data: dict[str, Any] = {
            "provider": "openai_http",
            "endpoint_path": endpoint_path,
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
        self._http_client = client or httpx.AsyncClient(timeout=self.config.timeout)
        self._speech_http_client = self._http_client
        self._image_http_clients: dict[bool, Any] = {}
        self._client: Any | None = None
        self._embedding_client: Any | None = None
        self._video_client: Any | None = None
        self._video_http_client: httpx.AsyncClient | None = None

    @classmethod
    def from_config(cls, config: ModelConfig | dict[str, Any] | str | None = None, **overrides: Any) -> "OpenAICompatibleHTTPModel":
        resolved = ModelConfig.from_any(config, **overrides)
        return cls(
            model=resolved.model,
            vision_model=resolved.vision_model,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
            endpoint_path=resolved.endpoint_path,
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

    def _get_client(self):
        if not self.config.base_url:
            raise ValueError("Chat base URL is not configured. Set `base_url` or `OPENAI_BASE_URL`.")
        if self._client is None:
            self._client = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=_HTTPChatCompletions(
                        client=self._http_client,
                        base_url=self.config.base_url,
                        endpoint_path=self.config.endpoint_path,
                        api_key=self.config.api_key,
                        auth_scheme=self.config.auth_scheme,
                        extra_headers=self.config.headers,
                    )
                ),
                embeddings=_HTTPEmbeddings(
                    client=self._http_client,
                    base_url=self.config.base_url,
                    endpoint_path=self.config.embedding_endpoint_path,
                    api_key=self.config.api_key,
                    auth_scheme=self.config.auth_scheme,
                    extra_headers=self.config.headers,
                ),
            )
        return self._client

    def _get_video_chat_completions(self):
        if self._video_client is None:
            self._video_http_client = httpx.AsyncClient(timeout=self.config.timeout, trust_env=not self.config.video_disable_env_proxy)
            self._video_client = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=_HTTPChatCompletions(
                        client=self._video_http_client,
                        base_url=self.config.video_base_url or self.config.base_url,
                        endpoint_path=self.config.endpoint_path,
                        api_key=self.config.video_api_key or self.config.api_key,
                        auth_scheme=self.config.auth_scheme,
                        extra_headers=self.config.headers,
                    )
                )
            )
        return self._video_client.chat.completions

    def _embeddings(self):
        embedding_api_key = self._embedding_api_key()
        embedding_base_url = self._embedding_base_url()
        if embedding_api_key == self.config.api_key and embedding_base_url == self.config.base_url:
            return self._get_client().embeddings
        if not embedding_base_url:
            raise ValueError(
                "Embedding base URL is not configured. Set `embedding_base_url`, `OPENAI_EMBEDDING_BASE_URL`, or `OPENAI_BASE_URL`."
            )
        if self._embedding_client is None:
            self._embedding_client = SimpleNamespace(
                embeddings=_HTTPEmbeddings(
                    client=self._http_client,
                    base_url=embedding_base_url,
                    endpoint_path=self.config.embedding_endpoint_path,
                    api_key=embedding_api_key,
                    auth_scheme=self.config.auth_scheme,
                    extra_headers=self.config.headers,
                )
            )
        return self._embedding_client.embeddings

    async def aclose(self) -> None:
        await super().aclose()
