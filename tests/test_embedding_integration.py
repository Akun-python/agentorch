import asyncio
import importlib.util
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, RateLimitError

import agentorch
from agentorch import EmbeddingCapableModelAdapter, OpenAICompatibleHTTPModel, OpenAIModel
from agentorch.config import ModelConfig


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "api接口" / "api_openai_embedding.py"


class FakeEmbeddings:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _embedding_response(vectors: list[list[float]], *, indexes: list[int] | None = None):
    resolved_indexes = indexes or list(range(len(vectors)))
    data = [
        SimpleNamespace(index=index, embedding=vector)
        for index, vector in zip(resolved_indexes, vectors, strict=True)
    ]
    return SimpleNamespace(data=data)


def _load_script_module():
    module_name = f"test_api_openai_embedding_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_api_exports_embedding_capability() -> None:
    assert hasattr(agentorch, "EmbeddingCapableModelAdapter")
    assert EmbeddingCapableModelAdapter is agentorch.EmbeddingCapableModelAdapter


def test_openai_model_embed_returns_vectors_and_embed_text_uses_defaults() -> None:
    asyncio.run(_test_openai_model_embed_returns_vectors_and_embed_text_uses_defaults())


async def _test_openai_model_embed_returns_vectors_and_embed_text_uses_defaults() -> None:
    fake_embeddings = FakeEmbeddings(
        [
            _embedding_response([[3.0, 4.0], [1.0, 2.0]], indexes=[1, 0]),
            _embedding_response([[0.1, 0.2, 0.3]]),
        ]
    )
    fake_client = SimpleNamespace(embeddings=fake_embeddings)
    model = OpenAIModel(
        model="gpt-4.1",
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        embedding_model="text-embedding-default",
    )
    model._client = fake_client

    vectors = await model.embed(["alpha", "beta"], embedding_model="text-embedding-custom", dimensions=64)
    vector = await model.embed_text("gamma")

    assert vectors == [[1.0, 2.0], [3.0, 4.0]]
    assert vector == [0.1, 0.2, 0.3]
    assert fake_embeddings.calls[0] == {
        "input": ["alpha", "beta"],
        "model": "text-embedding-custom",
        "dimensions": 64,
    }
    assert fake_embeddings.calls[1]["input"] == ["gamma"]
    assert fake_embeddings.calls[1]["model"] == model.config.embedding_model


def test_openai_model_embed_retries_after_transient_error() -> None:
    asyncio.run(_test_openai_model_embed_retries_after_transient_error())


async def _test_openai_model_embed_retries_after_transient_error() -> None:
    request = httpx.Request("POST", "https://example.test/embeddings")
    fake_embeddings = FakeEmbeddings(
        [
            APIConnectionError(message="temporary failure", request=request),
            _embedding_response([[9.0, 8.0]]),
        ]
    )
    model = OpenAIModel(
        model="gpt-4.1",
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        embedding_model="text-embedding-default",
        max_retries=1,
    )
    model._client = SimpleNamespace(embeddings=fake_embeddings)

    vectors = await model.embed(["retry"])

    assert vectors == [[9.0, 8.0]]
    assert len(fake_embeddings.calls) == 2


def test_openai_model_embed_retries_after_rate_limit_with_retry_after_header(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_test_openai_model_embed_retries_after_rate_limit_with_retry_after_header(monkeypatch))


async def _test_openai_model_embed_retries_after_rate_limit_with_retry_after_header(monkeypatch: pytest.MonkeyPatch) -> None:
    response = httpx.Response(429, headers={"retry-after": "2"}, request=httpx.Request("POST", "https://example.test/embeddings"))
    fake_embeddings = FakeEmbeddings(
        [
            RateLimitError("rate limited", response=response, body={"error": {"retry_after": 2}}),
            _embedding_response([[5.0, 6.0]]),
        ]
    )
    model = OpenAIModel(
        model="gpt-4.1",
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        embedding_model="text-embedding-default",
        max_retries=1,
        retry_jitter=0.0,
    )
    model._client = SimpleNamespace(embeddings=fake_embeddings)

    observed_delays: list[float] = []

    async def fake_sleep(delay: float):
        observed_delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    vectors = await model.embed(["rate-limit"])

    assert vectors == [[5.0, 6.0]]
    assert observed_delays
    assert observed_delays[0] == 2.0
    assert len(fake_embeddings.calls) == 2


def test_model_config_embedding_fields_normalize_and_use_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-chat-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://chat.example/v1")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "env-embedding-model")
    monkeypatch.setenv("OPENAI_EMBEDDING_DIMENSIONS", "256")
    monkeypatch.setenv("OPENAI_EMBEDDING_BASE_URL", "https://embed.example/v1/embeddings")

    env_config = ModelConfig()
    explicit_config = ModelConfig(
        api_key="explicit-chat-key",
        base_url="https://explicit.example/v1",
        embedding_base_url="https://explicit-embed.example/v1/embeddings",
        embedding_api_key=None,
    )

    assert env_config.embedding_api_key == "env-chat-key"
    assert env_config.embedding_base_url == "https://embed.example/v1"
    assert env_config.embedding_model == "env-embedding-model"
    assert env_config.embedding_dimensions == 256
    assert explicit_config.embedding_api_key == "explicit-chat-key"
    assert explicit_config.embedding_base_url == "https://explicit-embed.example/v1"


def test_openai_model_from_config_keeps_embedding_fields() -> None:
    model = OpenAIModel.from_config(
        {
            "model": "gpt-4.1-mini",
            "api_key": "test-key",
            "base_url": "https://chat.example/v1",
            "embedding_model": "text-embedding-3-large",
            "embedding_base_url": "https://embed.example/v1/embeddings",
            "embedding_dimensions": 512,
        }
    )

    assert model.config.embedding_model == "text-embedding-3-large"
    assert model.config.embedding_base_url == "https://embed.example/v1"
    assert model.config.embedding_dimensions == 512


def test_openai_compatible_http_model_embed_uses_custom_auth_headers_and_endpoint() -> None:
    asyncio.run(_test_openai_compatible_http_model_embed_uses_custom_auth_headers_and_endpoint())


async def _test_openai_compatible_http_model_embed_uses_custom_auth_headers_and_endpoint() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.25, 0.5, 0.75]}]},
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    model = OpenAICompatibleHTTPModel(
        model="chat-model",
        api_key="chat-key",
        base_url="https://chat.example/v1",
        auth_scheme="Token",
        headers={"X-Test": "1"},
        embedding_api_key="embed-key",
        embedding_base_url="https://embed.example/v2",
        embedding_endpoint_path="/vectorize",
        embedding_model="text-embedding-custom",
        client=client,
    )

    vectors = await model.embed(["custom http"], dimensions=128)

    assert vectors == [[0.25, 0.5, 0.75]]
    assert requests[0].url == httpx.URL("https://embed.example/v2/vectorize")
    assert requests[0].headers["Authorization"] == "Token embed-key"
    assert requests[0].headers["X-Test"] == "1"
    assert json.loads(requests[0].content.decode("utf-8")) == {
        "input": ["custom http"],
        "model": "text-embedding-custom",
        "dimensions": 128,
    }
    await model.aclose()


def test_api_openai_embedding_script_uses_agentorch_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    module = _load_script_module()
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OPENAI_EMBEDDING_INPUT=script text\nOPENAI_EMBEDDING_MODEL=script-embedding\nOPENAI_EMBEDDING_DIMENSIONS=8\n",
        encoding="utf-8",
    )

    observed: dict[str, object] = {}

    class FakeScriptModel:
        @classmethod
        def from_config(cls, config=None):
            observed["config"] = config
            return cls()

        async def embed_text(self, text: str, *, embedding_model: str | None = None, dimensions: int | None = None):
            observed["text"] = text
            observed["kwargs"] = {
                "embedding_model": embedding_model,
                "dimensions": dimensions,
            }
            return [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]

        async def aclose(self) -> None:
            observed["closed"] = True

    monkeypatch.setattr(module, "ENV_PATH", env_path)
    monkeypatch.setattr(module, "OpenAIModel", FakeScriptModel)

    module.main()
    output = capsys.readouterr().out

    assert observed["config"] is None
    assert observed["text"] == "script text"
    assert observed["kwargs"] == {
        "embedding_model": "script-embedding",
        "dimensions": 8,
    }
    assert observed["closed"] is True
    assert "Vector dimension: 6" in output
    assert "Vector first 5 values: [0.1, 0.2, 0.3, 0.4, 0.5]" in output
