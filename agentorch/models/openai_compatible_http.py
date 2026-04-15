from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from urllib.parse import urljoin

import httpx

from agentorch.config import ModelConfig

from .openai_model import OpenAIModel


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


class OpenAICompatibleHTTPModel(OpenAIModel):
    def __init__(
        self,
        model: str,
        vision_model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        endpoint_path: str = "/chat/completions",
        auth_scheme: str = "Bearer",
        headers: dict[str, str] | None = None,
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
        self.config = ModelConfig(
            provider="openai_http",
            model=model,
            vision_model=vision_model,
            api_key=api_key,
            base_url=base_url,
            endpoint_path=endpoint_path,
            auth_scheme=auth_scheme,
            headers=dict(headers or {}),
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            retry_base_delay=retry_base_delay,
            retry_max_delay=retry_max_delay,
            retry_jitter=retry_jitter,
            min_request_interval=min_request_interval,
            temperature=temperature,
        )
        if not self.config.base_url:
            raise ValueError("OpenAICompatibleHTTPModel requires base_url.")
        self._http_client = client or httpx.AsyncClient(timeout=self.config.timeout)
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
            )
        )

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
            max_tokens=resolved.max_tokens,
            timeout=resolved.timeout,
            max_retries=resolved.max_retries,
            retry_base_delay=resolved.retry_base_delay,
            retry_max_delay=resolved.retry_max_delay,
            retry_jitter=resolved.retry_jitter,
            min_request_interval=resolved.min_request_interval,
            temperature=resolved.temperature,
        )

    async def aclose(self) -> None:
        await self._http_client.aclose()
