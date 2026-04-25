import asyncio
import base64
import importlib.util
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from agentorch import ToolRegistry, create_agent
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.models import (
    ImageGenerationCapableModelAdapter,
    ImageGenerationResult,
    OpenAIModel,
    SpeechCapableModelAdapter,
    SpeechSynthesisResult,
    VideoAnalysisCapableModelAdapter,
)
from agentorch.tools import ToolError, create_analyze_video_tool, create_generate_image_tool


ROOT = Path(__file__).resolve().parents[1]
API_DIR = next(path for path in ROOT.iterdir() if path.is_dir() and path.name.startswith("api"))
IMAGE_SCRIPT_PATH = API_DIR / "api_图片生成.py"
VIDEO_SCRIPT_PATH = API_DIR / "api_视频理解.py"

PNG_BYTES = bytes.fromhex(
    "89504E470D0A1A0A"
    "0000000D49484452000000010000000108060000001F15C489"
    "0000000A49444154789C6360000002000154A24F5D00000000"
    "49454E44AE426082"
)


class FakeAsyncHTTPClient:
    def __init__(self, responses: list[httpx.Response | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    async def post(self, url: str, *, headers: dict[str, str] | None = None, json: dict[str, object] | None = None):
        self.calls.append({"url": url, "headers": dict(headers or {}), "json": dict(json or {})})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def aclose(self) -> None:
        return None


class FakeChatCompletions:
    def __init__(self, content: str = "video done", *, model_name: str = "video-model") -> None:
        self.content = content
        self.model_name = model_name
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            model=self.model_name,
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content, tool_calls=[]), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )


class FakeImageVideoModel(ImageGenerationCapableModelAdapter, VideoAnalysisCapableModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content="ok"),
            content="ok",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )

    async def generate_image(
        self,
        prompt: str,
        *,
        aspect_ratio: str | None = None,
        image_size: str | None = None,
        image_model: str | None = None,
        output_path: str | Path | None = None,
    ) -> ImageGenerationResult:
        target = Path(output_path or Path.cwd() / ".agentorch" / "images" / "fake-image")
        if not target.suffix:
            target = target.with_suffix(".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(PNG_BYTES)
        return ImageGenerationResult(
            output_path=str(target.resolve()),
            mime_type="image/png",
            bytes_written=len(PNG_BYTES),
            model=image_model or "fake-image-model",
            proxy_mode="disabled",
        )

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
        return ModelResponse(
            message=Message(role="assistant", content=f"analysis for: {prompt}"),
            content=f"analysis for: {prompt}",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
            raw=SimpleNamespace(model=model or "fake-video-model"),
        )


class FakeAllMediaModel(FakeImageVideoModel, SpeechCapableModelAdapter):
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
        target = Path(output_path or Path.cwd() / ".agentorch" / "audio" / "fake-audio")
        if not target.suffix:
            target = target.with_suffix(".mp3")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"audio")
        return SpeechSynthesisResult(
            output_path=str(target.resolve()),
            response_format=response_format or "mp3",
            content_type="audio/mpeg",
            bytes_written=target.stat().st_size,
            voice=voice or "alloy",
            speed=float(speed) if speed is not None else 1.0,
            model=speech_model or "tts-pro",
        )


class FakeImageOnlyModel(ImageGenerationCapableModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(content="ok")

    async def generate_image(
        self,
        prompt: str,
        *,
        aspect_ratio: str | None = None,
        image_size: str | None = None,
        image_model: str | None = None,
        output_path: str | Path | None = None,
    ) -> ImageGenerationResult:
        target = Path(output_path or Path.cwd() / "image-only.png")
        if not target.suffix:
            target = target.with_suffix(".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(PNG_BYTES)
        return ImageGenerationResult(
            output_path=str(target.resolve()),
            mime_type="image/png",
            bytes_written=len(PNG_BYTES),
            model=image_model or "image-only-model",
            proxy_mode="disabled",
        )


class NonMediaModel:
    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(content="ok")


def _image_response(*, mime_type: str = "image/png") -> httpx.Response:
    encoded = base64.b64encode(PNG_BYTES).decode("utf-8")
    return httpx.Response(
        200,
        headers={"Content-Type": "application/json"},
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "inlineData": {
                                    "data": encoded,
                                    "mimeType": mime_type,
                                }
                            }
                        ]
                    }
                }
            ]
        },
    )


def _load_script_module(path: Path):
    module_name = f"test_media_script_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_openai_model_generate_image_uses_fallback_models_and_explicit_url(tmp_path: Path):
    asyncio.run(_test_openai_model_generate_image_uses_fallback_models_and_explicit_url(tmp_path))


async def _test_openai_model_generate_image_uses_fallback_models_and_explicit_url(tmp_path: Path):
    fake_client = FakeAsyncHTTPClient(
        [
            httpx.Response(
                503,
                headers={"Content-Type": "application/json"},
                json={"error": {"message": "temporarily unavailable"}},
            ),
            _image_response(),
        ]
    )
    model = OpenAIModel(
        model="gpt-4.1-mini",
        api_key="chat-key",
        base_url="https://chat.example/v1",
        image_api_key="image-key",
        image_base_url="https://img.example",
        image_explicit_url="https://img.example/v1beta/models/{model}:generateContent",
        image_model="primary-model",
        image_fallback_models=["fallback-model"],
    )
    model._image_http_clients[True] = fake_client

    result = await model.generate_image("draw a city skyline", output_path=tmp_path / "city")

    assert fake_client.calls[0]["url"] == "https://img.example/v1beta/models/primary-model:generateContent"
    assert fake_client.calls[1]["url"] == "https://img.example/v1beta/models/fallback-model:generateContent"
    assert fake_client.calls[0]["headers"]["Authorization"] == "Bearer image-key"
    assert fake_client.calls[0]["headers"]["x-goog-api-key"] == "image-key"
    assert result.model == "fallback-model"
    assert result.proxy_mode == "env"
    assert Path(result.output_path).suffix == ".png"
    assert Path(result.output_path).read_bytes() == PNG_BYTES


def test_openai_model_generate_image_retries_without_proxy(tmp_path: Path):
    asyncio.run(_test_openai_model_generate_image_retries_without_proxy(tmp_path))


async def _test_openai_model_generate_image_retries_without_proxy(tmp_path: Path):
    env_client = FakeAsyncHTTPClient([httpx.ProxyError("proxy failed")])
    no_proxy_client = FakeAsyncHTTPClient([_image_response()])
    model = OpenAIModel(
        model="gpt-4.1-mini",
        api_key="chat-key",
        base_url="https://chat.example/v1",
        image_api_key="image-key",
        image_base_url="https://img.example",
        image_model="proxy-model",
        image_retry_without_proxy=True,
    )
    model._image_http_clients[True] = env_client
    model._image_http_clients[False] = no_proxy_client

    result = await model.generate_image("draw a mountain", output_path=tmp_path / "mountain")

    assert env_client.calls[0]["url"] == "https://img.example/v1beta/models/proxy-model:generateContent"
    assert no_proxy_client.calls[0]["url"] == "https://img.example/v1beta/models/proxy-model:generateContent"
    assert result.proxy_mode == "disabled-after-proxy-error"
    assert Path(result.output_path).exists()


def test_openai_model_generate_image_error_paths(tmp_path: Path):
    asyncio.run(_test_openai_model_generate_image_error_paths(tmp_path))


async def _test_openai_model_generate_image_error_paths(tmp_path: Path):
    missing_key_model = OpenAIModel(
        model="gpt-4.1-mini",
        api_key="",
        base_url="https://chat.example/v1",
        image_api_key="",
        image_base_url="https://img.example",
    )
    with pytest.raises(ValueError, match="Image API key is not configured"):
        await missing_key_model.generate_image("hello")

    malformed_client = FakeAsyncHTTPClient(
        [
            httpx.Response(
                200,
                headers={"Content-Type": "application/json"},
                json={"candidates": [{"content": {"parts": []}}]},
            )
        ]
    )
    malformed_model = OpenAIModel(
        model="gpt-4.1-mini",
        api_key="chat-key",
        base_url="https://chat.example/v1",
        image_api_key="image-key",
        image_base_url="https://img.example",
        image_model="malformed-model",
    )
    malformed_model._image_http_clients[True] = malformed_client
    with pytest.raises(RuntimeError, match="did not include inlineData"):
        await malformed_model.generate_image("hello", output_path=tmp_path / "bad-image")

    fallback_fail_client = FakeAsyncHTTPClient(
        [
            httpx.Response(503, headers={"Content-Type": "application/json"}, json={"error": {"message": "temporarily unavailable"}}),
            httpx.Response(503, headers={"Content-Type": "application/json"}, json={"error": {"message": "temporarily unavailable"}}),
        ]
    )
    fallback_fail_model = OpenAIModel(
        model="gpt-4.1-mini",
        api_key="chat-key",
        base_url="https://chat.example/v1",
        image_api_key="image-key",
        image_base_url="https://img.example",
        image_model="gemini-3-pro-image-preview",
        image_fallback_models=["gemini-3.1-flash-image-preview"],
    )
    fallback_fail_model._image_http_clients[True] = fallback_fail_client
    with pytest.raises(RuntimeError, match="Image generation failed"):
        await fallback_fail_model.generate_image("hello", output_path=tmp_path / "fail-image")


def test_openai_model_analyze_video_builds_multimodal_request(tmp_path: Path):
    asyncio.run(_test_openai_model_analyze_video_builds_multimodal_request(tmp_path))


async def _test_openai_model_analyze_video_builds_multimodal_request(tmp_path: Path):
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"fake video bytes")
    fake_chat = FakeChatCompletions(model_name="override-video-model")
    model = OpenAIModel(
        model="gpt-4.1-mini",
        api_key="chat-key",
        base_url="https://chat.example/v1",
        video_api_key="video-key",
        video_base_url="https://video.example/v1",
        video_model="default-video-model",
    )
    model._video_client = SimpleNamespace(chat=SimpleNamespace(completions=fake_chat))

    response = await model.analyze_video(
        prompt="Summarize this video",
        video_path=video_path,
        model="override-video-model",
        max_tokens=111,
        temperature=0.2,
    )

    assert response.content == "video done"
    assert fake_chat.calls[0]["model"] == "override-video-model"
    assert fake_chat.calls[0]["max_tokens"] == 111
    assert fake_chat.calls[0]["temperature"] == 0.2
    content = fake_chat.calls[0]["messages"][0]["content"]
    assert content[0]["text"] == "Summarize this video"
    assert content[1]["mime_type"] == "video/mp4"
    assert content[1]["image_url"]["url"].startswith("data:video/mp4;base64,")


def test_openai_model_analyze_video_error_paths(tmp_path: Path):
    asyncio.run(_test_openai_model_analyze_video_error_paths(tmp_path))


async def _test_openai_model_analyze_video_error_paths(tmp_path: Path):
    model = OpenAIModel(
        model="gpt-4.1-mini",
        api_key="chat-key",
        base_url="https://chat.example/v1",
        video_api_key="video-key",
        video_base_url="https://video.example/v1",
    )
    with pytest.raises(ValueError, match="Video analysis prompt cannot be empty"):
        await model.analyze_video(prompt="", video_path=tmp_path / "sample.mp4")
    with pytest.raises(FileNotFoundError, match="Media file not found"):
        await model.analyze_video(prompt="hello", video_path=tmp_path / "missing.mp4")


def test_media_tools_execute_and_block_workspace_escape(tmp_path: Path):
    asyncio.run(_test_media_tools_execute_and_block_workspace_escape(tmp_path))


async def _test_media_tools_execute_and_block_workspace_escape(tmp_path: Path):
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"clip bytes")
    registry = ToolRegistry.from_tools(
        create_generate_image_tool(FakeImageVideoModel(), tmp_path),
        create_analyze_video_tool(FakeImageVideoModel(), tmp_path),
    )

    image_result = await registry.execute("generate_image", {"prompt": "tool image", "output_path": "artifacts/image"})
    assert image_result.success is True
    assert Path(image_result.data["output_path"]).exists()

    video_result = await registry.execute(
        "analyze_video",
        {"question": "what is happening", "video_path": "clip.mp4", "save_outputs": True},
    )
    assert video_result.success is True
    assert "analysis_text" in video_result.data
    assert Path(video_result.data["txt_output_path"]).exists()
    assert Path(video_result.data["json_output_path"]).exists()

    with pytest.raises(ToolError, match="outside the allowed workspace"):
        await registry.execute("generate_image", {"prompt": "escape", "output_path": "../escape.png"})
    with pytest.raises(ToolError, match="outside the allowed workspace"):
        await registry.execute("analyze_video", {"question": "escape", "video_path": "../clip.mp4"})


def test_generate_image_tool_uses_extended_timeout_from_model_config(tmp_path: Path):
    model = FakeImageVideoModel()
    model.config = SimpleNamespace(image_timeout=90.0)

    tool = create_generate_image_tool(model, tmp_path)

    assert tool.spec.timeout == 105.0


def test_create_agent_with_media_bundle_registers_supported_media_tools():
    all_media_agent = create_agent(
        model=FakeAllMediaModel(),
        tool_bundles={"include_filesystem": False, "include_execution": False, "include_git": False, "include_media": True},
    )
    image_only_agent = create_agent(
        model=FakeImageOnlyModel(),
        tool_bundles={"include_filesystem": False, "include_execution": False, "include_git": False, "include_media": True},
    )

    assert set(all_media_agent.export_blueprint()["runtime"]["tools"]) == {"text_to_speech", "generate_image", "analyze_video"}
    assert image_only_agent.export_blueprint()["runtime"]["tools"] == ["generate_image"]


def test_create_agent_with_media_bundle_rejects_models_without_media_capabilities():
    with pytest.raises(ValueError, match="at least one media capability"):
        create_agent(
            model=NonMediaModel(),
            tool_bundles={"include_filesystem": False, "include_execution": False, "include_git": False, "include_media": True},
        )


def test_image_script_wrapper_uses_agentorch_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    asyncio.run(_test_image_script_wrapper_uses_agentorch_model(monkeypatch, tmp_path))


async def _test_image_script_wrapper_uses_agentorch_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    module = _load_script_module(IMAGE_SCRIPT_PATH)
    env_path = tmp_path / ".env"
    for name in (
        "APIYI_GEN_PROMPT",
        "APIYI_GEN_OUTPUT",
        "APIYI_GEN_OUTPUT_DIR",
        "APIYI_GEN_ASPECT_RATIO",
        "APIYI_GEN_IMAGE_SIZE",
        "APIYI_GEN_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    env_path.write_text(
        "\n".join(
            [
                "APIYI_GEN_PROMPT=script image prompt",
                "APIYI_GEN_OUTPUT=generated/image",
                "APIYI_GEN_OUTPUT_DIR=out",
            ]
        ),
        encoding="utf-8",
    )

    observed: dict[str, object] = {}

    class FakeScriptImageModel:
        @classmethod
        def from_config(cls, config=None):
            return cls()

        async def generate_image(self, prompt: str, **kwargs):
            observed["prompt"] = prompt
            observed["kwargs"] = dict(kwargs)
            target = Path(kwargs["output_path"])
            if not target.suffix:
                target = target.with_suffix(".png")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(PNG_BYTES)
            return ImageGenerationResult(
                output_path=str(target.resolve()),
                mime_type="image/png",
                bytes_written=len(PNG_BYTES),
                model="script-image-model",
                proxy_mode="disabled",
            )

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(module, "ENV_PATH", env_path)
    monkeypatch.setattr(module, "SCRIPT_DIR", tmp_path)
    monkeypatch.setattr(module, "OpenAIModel", FakeScriptImageModel)

    result = await module.generate_from_env()

    assert observed["prompt"] == "script image prompt"
    assert Path(result.output_path).exists()
    assert Path(result.output_path).name == "image.png"
    assert Path(observed["kwargs"]["output_path"]).parent == tmp_path / "out" / "generated"


def test_video_script_wrapper_uses_agentorch_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    asyncio.run(_test_video_script_wrapper_uses_agentorch_model(monkeypatch, tmp_path))


async def _test_video_script_wrapper_uses_agentorch_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    module = _load_script_module(VIDEO_SCRIPT_PATH)
    env_path = tmp_path / ".env"
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"clip bytes")
    for name in (
        "APIYI_VIDEO_QUESTION",
        "APIYI_VIDEO_PATH",
        "APIYI_VIDEO_MIME_TYPE",
        "OPENAI_VIDEO_MODEL",
        "VIDEO_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    env_path.write_text(
        "\n".join(
            [
                "APIYI_VIDEO_QUESTION=what is in this clip?",
                "APIYI_VIDEO_PATH=clip.mp4",
                "OPENAI_VIDEO_MODEL=video-script-model",
            ]
        ),
        encoding="utf-8",
    )

    observed: dict[str, object] = {}

    class FakeScriptVideoModel:
        config = SimpleNamespace(video_model="video-script-model", model="chat-model")

        @classmethod
        def from_config(cls, config=None):
            return cls()

        async def analyze_video(self, **kwargs):
            observed["kwargs"] = dict(kwargs)
            return ModelResponse(
                message=Message(role="assistant", content="script video result"),
                content="script video result",
                finish_reason="stop",
                usage=UsageInfo(total_tokens=1),
                raw=SimpleNamespace(model="video-script-model"),
            )

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(module, "ENV_PATH", env_path)
    monkeypatch.setattr(module, "SCRIPT_DIR", tmp_path)
    monkeypatch.setattr(module, "OpenAIModel", FakeScriptVideoModel)

    result = await module.analyze_from_env(save_outputs=True)

    assert observed["kwargs"]["prompt"] == "what is in this clip?"
    assert Path(observed["kwargs"]["video_path"]) == video_path
    assert result["analysis_text"] == "script video result"
    assert Path(result["txt_output_path"]).exists()
    assert Path(result["json_output_path"]).exists()
