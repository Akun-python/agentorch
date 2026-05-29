from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from agentorch.config import MemoryConfig
from agentorch.core import Message, ModelRequest, ToolCall
from agentorch.memory import MemoryManager
from agentorch.models.openai_model import OpenAIModel


def test_openai_model_includes_reasoning_content_in_assistant_message_payload() -> None:
    model = OpenAIModel(
        model="deepseek-v4-pro",
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        provider_options={"reasoning_effort": "max"},
    )
    message = Message(
        role="assistant",
        content="我先查一下。",
        reasoning_content="需要先定位文件，再决定是否调用工具。",
        tool_calls=[ToolCall(id="call_1", name="read_file", arguments={"path": "README.md"})],
    )

    payload = model._build_payload(ModelRequest(messages=[message]), stream=False)

    serialized = payload["messages"][0]
    assert serialized["reasoning_content"] == "需要先定位文件，再决定是否调用工具。"
    assert payload["reasoning_effort"] == "max"
    assert payload["thinking"] == {"type": "enabled"}


def test_openai_model_normalizes_reasoning_content_from_response() -> None:
    model = OpenAIModel(model="deepseek-v4-pro", api_key="sk-test", base_url="https://api.deepseek.com")
    raw = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(
                    content="已完成。",
                    reasoning_content="先搜索，再改文件。",
                    tool_calls=[
                        SimpleNamespace(
                            id="call_1",
                            function=SimpleNamespace(name="read_file", arguments='{"path":"README.md"}'),
                        )
                    ],
                ),
            )
        ],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    )

    response = model._normalize_response(raw)

    assert response.reasoning_content == "先搜索，再改文件。"
    assert response.message is not None
    assert response.message.reasoning_content == "先搜索，再改文件。"
    assert response.message.tool_calls[0].name == "read_file"


def test_memory_manager_persists_reasoning_content(tmp_path: Path) -> None:
    memory = MemoryManager(
        config=MemoryConfig(
            persist_thread_messages=True,
            checkpoint_path=tmp_path / "checkpoints.db",
            record_path=tmp_path / "records.db",
        )
    )
    message = Message(role="assistant", content="最终答案", reasoning_content="这是中间思考")

    import asyncio

    asyncio.run(memory.append_message("thread-1", message))
    restored = asyncio.run(memory.load_persisted_thread_messages("thread-1"))

    assert restored
    assert restored[0].reasoning_content == "这是中间思考"
