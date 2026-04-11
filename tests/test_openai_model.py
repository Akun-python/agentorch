import asyncio
from pathlib import Path
from types import SimpleNamespace

from agentorch.core import Message, ToolCall
from agentorch.models import OpenAIModel


def test_openai_message_conversion_includes_tool_calls():
    model = OpenAIModel(model="gpt-4.1", api_key="test-key", base_url="https://api.openai.com/v1")
    message = Message(
        role="assistant",
        content="",
        tool_calls=[ToolCall(id="call-1", name="lookup", arguments={"query": "weather"})],
    )
    payload = model._message_to_openai(message)
    assert payload["role"] == "assistant"
    assert payload["content"] is None
    assert payload["tool_calls"][0]["id"] == "call-1"
    assert payload["tool_calls"][0]["function"]["name"] == "lookup"


def test_openai_message_conversion_supports_multimodal_content():
    model = OpenAIModel(model="gpt-4.1", api_key="test-key", base_url="https://api.openai.com/v1")
    message = Message(
        role="user",
        content="",
        metadata={
            "multimodal_content": [
                {"type": "text", "text": "describe this image"},
                {"type": "image_url", "image_url": {"url": "https://example.com/image.png"}},
            ]
        },
    )

    payload = model._message_to_openai(message)

    assert isinstance(payload["content"], list)
    assert payload["content"][0]["text"] == "describe this image"
    assert payload["content"][1]["image_url"]["url"] == "https://example.com/image.png"


def test_openai_model_analyze_image_uses_configured_vision_model(tmp_path: Path):
    asyncio.run(_test_openai_model_analyze_image_uses_configured_vision_model(tmp_path))


async def _test_openai_model_analyze_image_uses_configured_vision_model(tmp_path: Path):
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(
        bytes.fromhex(
            "89504E470D0A1A0A"
            "0000000D49484452000000010000000108060000001F15C489"
            "0000000A49444154789C6360000002000154A24F5D00000000"
            "49454E44AE426082"
        )
    )

    class FakeChatCompletions:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def create(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="done", tool_calls=[]), finish_reason="stop")],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            )

    fake_chat = FakeChatCompletions()
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=fake_chat))
    model = OpenAIModel(model="gpt-4.1-mini", vision_model="gpt-4.1-vision", api_key="test-key", base_url="https://api.openai.com/v1")
    model._client = fake_client

    response = await model.analyze_image(prompt="describe this image", image_path=image_path)

    assert response.content == "done"
    assert fake_chat.calls[0]["model"] == "gpt-4.1-vision"
    request_messages = fake_chat.calls[0]["messages"]
    assert isinstance(request_messages, list)
    assert request_messages[0]["content"][0]["text"] == "describe this image"
