import asyncio
import importlib.util
import uuid
from pathlib import Path

import httpx
import pytest

from agentorch import OpenAICompatibleHTTPModel, OpenAIModel, ToolRegistry, create_agent
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.models import SpeechCapableModelAdapter, SpeechSynthesisResult
from agentorch.tools import ToolError, create_text_to_speech_tool


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "api接口" / "api_openai语音.py"


class FakeSpeechClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    async def post(self, url: str, *, headers: dict[str, str] | None = None, json: dict[str, object] | None = None):
        self.calls.append({"url": url, "headers": dict(headers or {}), "json": dict(json or {})})
        return self.responses.pop(0)

    async def aclose(self) -> None:
        return None


class FakeSpeechModel(SpeechCapableModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content="ok"),
            content="ok",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )

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
        target = Path(output_path or Path.cwd() / ".agentorch" / "audio" / "fake.mp3")
        if target.exists() and target.is_dir():
            target = target / "fake.mp3"
        elif not target.suffix:
            target = target.with_suffix(".mp3")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"audio:{text}".encode("utf-8"))
        return SpeechSynthesisResult(
            output_path=str(target.resolve()),
            response_format=response_format or "mp3",
            content_type="audio/mpeg",
            bytes_written=target.stat().st_size,
            voice=voice or "alloy",
            speed=float(speed) if speed is not None else 1.0,
            model=speech_model or "tts-pro",
        )


class NonMediaModel:
    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(content="ok")


def _load_script_module():
    module_name = f"test_api_openai_speech_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_openai_model_synthesize_speech_writes_audio_and_normalizes_full_endpoint(tmp_path: Path):
    asyncio.run(_test_openai_model_synthesize_speech_writes_audio_and_normalizes_full_endpoint(tmp_path))


async def _test_openai_model_synthesize_speech_writes_audio_and_normalizes_full_endpoint(tmp_path: Path):
    response = httpx.Response(200, headers={"Content-Type": "audio/mpeg"}, content=b"ID3test-audio")
    fake_client = FakeSpeechClient([response])
    model = OpenAIModel(
        model="gpt-4.1-mini",
        api_key="chat-key",
        base_url="https://chat.example/v1",
        speech_api_key="speech-key",
        speech_base_url="https://speech.example/v1/audio/speech",
        speech_model="tts-test-model",
        speech_voice="voice-test",
    )
    model._speech_http_client = fake_client

    result = await model.synthesize_speech("hello speech", output_path=tmp_path / "greeting")

    assert model.config.speech_base_url == "https://speech.example/v1"
    assert fake_client.calls[0]["url"] == "https://speech.example/v1/audio/speech"
    assert fake_client.calls[0]["json"] == {
        "model": "tts-test-model",
        "input": "hello speech",
        "voice": "voice-test",
        "speed": 1.0,
        "response_format": "mp3",
    }
    assert Path(result.output_path).suffix == ".mp3"
    assert Path(result.output_path).read_bytes() == b"ID3test-audio"
    assert result.bytes_written == len(b"ID3test-audio")


def test_openai_compatible_http_model_synthesize_speech_uses_custom_auth_and_headers(tmp_path: Path):
    asyncio.run(_test_openai_compatible_http_model_synthesize_speech_uses_custom_auth_and_headers(tmp_path))


async def _test_openai_compatible_http_model_synthesize_speech_uses_custom_auth_and_headers(tmp_path: Path):
    response = httpx.Response(200, headers={"Content-Type": "audio/wav"}, content=b"RIFFtest-audio")
    fake_client = FakeSpeechClient([response])
    model = OpenAICompatibleHTTPModel(
        model="chat-model",
        api_key="chat-key",
        base_url="https://chat.example/v1",
        auth_scheme="Token",
        headers={"X-Test": "1"},
        speech_api_key="speech-key",
        speech_base_url="https://speech.example/v2",
        speech_endpoint_path="/speech",
        speech_model="tts-custom",
        speech_voice="voice-custom",
        speech_format="wav",
        client=httpx.AsyncClient(),
    )
    model._speech_http_client = fake_client

    result = await model.synthesize_speech("custom audio", output_path=tmp_path / "custom.wav")

    assert fake_client.calls[0]["url"] == "https://speech.example/v2/speech"
    assert fake_client.calls[0]["headers"]["Authorization"] == "Token speech-key"
    assert fake_client.calls[0]["headers"]["X-Test"] == "1"
    assert fake_client.calls[0]["json"]["model"] == "tts-custom"
    assert result.response_format == "wav"
    await model.aclose()


def test_speech_synthesis_error_paths(tmp_path: Path):
    asyncio.run(_test_speech_synthesis_error_paths(tmp_path))


async def _test_speech_synthesis_error_paths(tmp_path: Path):
    missing_key_model = OpenAICompatibleHTTPModel(
        model="chat-model",
        api_key="",
        base_url="https://chat.example/v1",
        speech_api_key="",
        speech_base_url="https://speech.example/v1",
        speech_model="tts-test-model",
        speech_voice="voice-test",
        client=httpx.AsyncClient(),
    )
    with pytest.raises(ValueError, match="Speech API key is not configured"):
        await missing_key_model.synthesize_speech("hello")

    ok_model = OpenAIModel(
        model="gpt-4.1-mini",
        api_key="chat-key",
        base_url="https://chat.example/v1",
        speech_api_key="speech-key",
        speech_base_url="https://speech.example/v1",
        speech_model="tts-test-model",
        speech_voice="voice-test",
    )
    with pytest.raises(ValueError, match="Unsupported speech response format"):
        await ok_model.synthesize_speech("hello", response_format="unknown")
    with pytest.raises(ValueError, match="Speech speed must be numeric"):
        await ok_model.synthesize_speech("hello", speed="fast")

    failing_client = FakeSpeechClient(
        [
            httpx.Response(
                500,
                headers={"Content-Type": "application/json"},
                json={"error": {"message": "boom"}},
            ),
            httpx.Response(200, headers={"Content-Type": "text/plain"}, text="not audio"),
        ]
    )
    ok_model._speech_http_client = failing_client
    with pytest.raises(RuntimeError, match="Speech synthesis request failed"):
        await ok_model.synthesize_speech("hello", output_path=tmp_path / "fail.mp3")
    with pytest.raises(RuntimeError, match="Speech synthesis response is not audio"):
        await ok_model.synthesize_speech("hello", output_path=tmp_path / "not-audio.mp3")


def test_text_to_speech_tool_executes_and_blocks_workspace_escape(tmp_path: Path):
    asyncio.run(_test_text_to_speech_tool_executes_and_blocks_workspace_escape(tmp_path))


async def _test_text_to_speech_tool_executes_and_blocks_workspace_escape(tmp_path: Path):
    registry = ToolRegistry.from_tools(create_text_to_speech_tool(FakeSpeechModel(), tmp_path))

    result = await registry.execute("text_to_speech", {"text": "tool audio", "response_format": "wav"})

    assert result.success is True
    assert result.data["response_format"] == "wav"
    assert Path(result.data["output_path"]).exists()

    with pytest.raises(ToolError, match="outside the allowed workspace"):
        await registry.execute("text_to_speech", {"text": "escape", "output_path": "../escape.mp3"})


def test_create_agent_with_media_bundle_registers_tts_tool():
    agent = create_agent(
        model=FakeSpeechModel(),
        tool_bundles={"include_filesystem": False, "include_execution": False, "include_git": False, "include_media": True},
    )

    assert "text_to_speech" in agent.export_blueprint()["runtime"]["tools"]


def test_create_agent_with_media_bundle_rejects_non_media_model():
    with pytest.raises(ValueError, match="at least one media capability"):
        create_agent(
            model=NonMediaModel(),
            tool_bundles={"include_filesystem": False, "include_execution": False, "include_git": False, "include_media": True},
        )


def test_api_openai_speech_script_uses_agentorch_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    asyncio.run(_test_api_openai_speech_script_uses_agentorch_model(monkeypatch, tmp_path))


async def _test_api_openai_speech_script_uses_agentorch_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    module = _load_script_module()
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_TTS_INPUT=script text\nOPENAI_TTS_OUTPUT_PATH=generated/script-audio\n", encoding="utf-8")

    observed: dict[str, object] = {}

    class FakeScriptModel(FakeSpeechModel):
        @classmethod
        def from_config(cls, config=None):
            return cls()

        async def synthesize_speech(self, text: str, **kwargs):
            observed["text"] = text
            observed["kwargs"] = dict(kwargs)
            return await super().synthesize_speech(text, **kwargs)

    monkeypatch.setattr(module, "ENV_PATH", env_path)
    monkeypatch.setattr(module, "OpenAIModel", FakeScriptModel)

    result = await module.synthesize_from_env()

    assert observed["text"] == "script text"
    assert Path(result.output_path).exists()
    assert Path(result.output_path).name == "script-audio.mp3"
