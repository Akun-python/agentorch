from agentorch.config import ModelConfig


def test_explicit_base_credentials_override_env_backed_capability_defaults(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-chat-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://env-chat.example/v1")
    monkeypatch.setenv("OPENAI_EMBEDDING_API_KEY", "env-embed-key")
    monkeypatch.setenv("OPENAI_EMBEDDING_BASE_URL", "https://env-embed.example/v1/embeddings")
    monkeypatch.setenv("OPENAI_TTS_API_KEY", "env-speech-key")
    monkeypatch.setenv("OPENAI_TTS_BASE_URL", "https://env-speech.example/v1/audio/speech")
    monkeypatch.setenv("OPENAI_IMAGE_API_KEY", "env-image-key")
    monkeypatch.setenv("OPENAI_VIDEO_API_KEY", "env-video-key")
    monkeypatch.setenv("OPENAI_VIDEO_BASE_URL", "https://env-video.example/v1/chat/completions")

    config = ModelConfig(
        api_key="explicit-chat-key",
        base_url="https://explicit.example/v1",
    )

    assert config.api_key == "explicit-chat-key"
    assert config.base_url == "https://explicit.example/v1"
    assert config.embedding_api_key == "explicit-chat-key"
    assert config.embedding_base_url == "https://explicit.example/v1"
    assert config.speech_api_key == "explicit-chat-key"
    assert config.speech_base_url == "https://explicit.example/v1"
    assert config.image_api_key == "explicit-chat-key"
    assert config.video_api_key == "explicit-chat-key"
    assert config.video_base_url == "https://explicit.example/v1"


def test_explicit_capability_credentials_still_beat_explicit_base(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_EMBEDDING_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_TTS_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_TTS_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_IMAGE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_VIDEO_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_VIDEO_BASE_URL", raising=False)

    config = ModelConfig(
        api_key="explicit-chat-key",
        base_url="https://explicit.example/v1",
        embedding_api_key="explicit-embed-key",
        embedding_base_url="https://explicit-embed.example/v1/embeddings",
        speech_api_key="explicit-speech-key",
        speech_base_url="https://explicit-speech.example/v1/audio/speech",
        image_api_key="explicit-image-key",
        video_api_key="explicit-video-key",
        video_base_url="https://explicit-video.example/v1/chat/completions",
    )

    assert config.embedding_api_key == "explicit-embed-key"
    assert config.embedding_base_url == "https://explicit-embed.example/v1"
    assert config.speech_api_key == "explicit-speech-key"
    assert config.speech_base_url == "https://explicit-speech.example/v1"
    assert config.image_api_key == "explicit-image-key"
    assert config.video_api_key == "explicit-video-key"
    assert config.video_base_url == "https://explicit-video.example/v1"
