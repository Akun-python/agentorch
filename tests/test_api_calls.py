import asyncio
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, RateLimitError

from agentorch.core import Message, ModelRequest
from agentorch.models import OpenAIModel
from agentorch.sandbox import SandboxManager, SandboxPolicy
from agentorch.tools import (
    ToolRegistry,
    create_append_file_tool,
    create_git_diff_summary_tool,
    create_git_recent_commits_tool,
    create_git_status_tool,
    create_replace_in_file_tool,
    create_run_command_tool,
)


def _build_openai_response(*, content: str = "", finish_reason: str = "stop", tool_calls: list[object] | None = None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    usage = SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18)
    return SimpleNamespace(choices=[choice], usage=usage)


class FakeChatCompletions:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeStreamingResponse:
    def __init__(self, chunks: list[object]) -> None:
        self._chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


def test_openai_model_generate_normalizes_tool_calls_and_usage():
    asyncio.run(_test_openai_model_generate_normalizes_tool_calls_and_usage())


async def _test_openai_model_generate_normalizes_tool_calls_and_usage():
    tool_call = SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(name="lookup", arguments='{"query": "weather"}'),
    )
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeChatCompletions([_build_openai_response(tool_calls=[tool_call])])))
    model = OpenAIModel(model="gpt-4.1", api_key="test-key", base_url="https://api.openai.com/v1")
    model._client = fake_client

    request = ModelRequest(messages=[Message(role="user", content="check weather")], tools=[{"type": "function", "function": {"name": "lookup"}}])
    response = await model.generate(request)

    assert response.tool_calls[0].name == "lookup"
    assert response.tool_calls[0].arguments == {"query": "weather"}
    assert response.usage.total_tokens == 18
    assert fake_client.chat.completions.calls[0]["stream"] is False


def test_openai_model_generate_retries_after_transient_error():
    asyncio.run(_test_openai_model_generate_retries_after_transient_error())


async def _test_openai_model_generate_retries_after_transient_error():
    request = httpx.Request("POST", "https://example.test/chat/completions")
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=FakeChatCompletions(
                [
                    APIConnectionError(message="temporary failure", request=request),
                    _build_openai_response(content="Recovered."),
                ]
            )
        )
    )
    model = OpenAIModel(model="gpt-4.1", api_key="test-key", base_url="https://api.openai.com/v1", max_retries=1)
    model._client = fake_client

    request = ModelRequest(messages=[Message(role="user", content="hello")])
    response = await model.generate(request)

    assert response.content == "Recovered."
    assert len(fake_client.chat.completions.calls) == 2


def test_openai_model_generate_retries_after_rate_limit_with_retry_after_header(monkeypatch):
    asyncio.run(_test_openai_model_generate_retries_after_rate_limit_with_retry_after_header(monkeypatch))


async def _test_openai_model_generate_retries_after_rate_limit_with_retry_after_header(monkeypatch):
    response = httpx.Response(429, headers={"retry-after": "3"}, request=httpx.Request("POST", "https://example.test/chat/completions"))
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=FakeChatCompletions(
                [
                    RateLimitError("rate limited", response=response, body={"error": {"retry_after": 3}}),
                    _build_openai_response(content="Recovered after 429."),
                ]
            )
        )
    )
    model = OpenAIModel(
        model="gpt-4.1",
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        max_retries=1,
        retry_jitter=0.0,
    )
    model._client = fake_client

    observed_delays: list[float] = []

    async def fake_sleep(delay: float):
        observed_delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    request = ModelRequest(messages=[Message(role="user", content="hello")])
    response_obj = await model.generate(request)

    assert response_obj.content == "Recovered after 429."
    assert observed_delays
    assert observed_delays[0] == 3.0
    assert len(fake_client.chat.completions.calls) == 2


def test_openai_model_stream_normalizes_delta_and_tool_calls():
    asyncio.run(_test_openai_model_stream_normalizes_delta_and_tool_calls())


async def _test_openai_model_stream_normalizes_delta_and_tool_calls():
    first_chunk = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=None,
                delta=SimpleNamespace(content="Hel", tool_calls=None),
            )
        ]
    )
    second_chunk = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls",
                delta=SimpleNamespace(
                    content="lo",
                    tool_calls=[
                        SimpleNamespace(
                            id="call-2",
                            function=SimpleNamespace(name="math", arguments='{"value": 3}'),
                        )
                    ],
                ),
            )
        ]
    )
    fake_stream = FakeStreamingResponse([first_chunk, second_chunk])
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeChatCompletions([fake_stream])))
    model = OpenAIModel(model="gpt-4.1", api_key="test-key", base_url="https://api.openai.com/v1")
    model._client = fake_client

    request = ModelRequest(messages=[Message(role="user", content="stream")])
    chunks = [chunk async for chunk in model.stream(request)]

    assert chunks[0].delta_text == "Hel"
    assert chunks[1].delta_text == "lo"
    assert chunks[1].tool_calls[0].name == "math"
    assert chunks[1].tool_calls[0].arguments == {"value": 3}
    assert fake_client.chat.completions.calls[0]["stream"] is True


def test_openai_model_stream_reassembles_fragmented_tool_call_arguments():
    asyncio.run(_test_openai_model_stream_reassembles_fragmented_tool_call_arguments())


async def _test_openai_model_stream_reassembles_fragmented_tool_call_arguments():
    first_chunk = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=None,
                delta=SimpleNamespace(
                    content="",
                    tool_calls=[
                        SimpleNamespace(
                            id="call-3",
                            index=0,
                            function=SimpleNamespace(name="generate_image", arguments=""),
                        )
                    ],
                ),
            )
        ]
    )
    second_chunk = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=None,
                delta=SimpleNamespace(
                    content="",
                    tool_calls=[
                        SimpleNamespace(
                            id=None,
                            index=0,
                            function=SimpleNamespace(name=None, arguments='{"prompt":"yangguo and eagle ally'),
                        )
                    ],
                ),
            )
        ]
    )
    third_chunk = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls",
                delta=SimpleNamespace(
                    content="",
                    tool_calls=[
                        SimpleNamespace(
                            id=None,
                            index=0,
                            function=SimpleNamespace(name=None, arguments='","output_path":"artifacts/yangguo.png"}'),
                        )
                    ],
                ),
            )
        ]
    )
    fake_stream = FakeStreamingResponse([first_chunk, second_chunk, third_chunk])
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeChatCompletions([fake_stream])))
    model = OpenAIModel(model="gpt-4.1", api_key="test-key", base_url="https://api.openai.com/v1")
    model._client = fake_client

    request = ModelRequest(messages=[Message(role="user", content="stream tool args")])
    chunks = [chunk async for chunk in model.stream(request)]

    assert chunks[0].tool_calls[0].name == "generate_image"
    assert chunks[0].tool_calls[0].arguments == {}
    assert chunks[1].tool_calls[0].name == "generate_image"
    assert chunks[1].tool_calls[0].arguments == {}
    assert chunks[2].tool_calls[0].name == "generate_image"
    assert chunks[2].tool_calls[0].arguments == {
        "prompt": "yangguo and eagle ally",
        "output_path": "artifacts/yangguo.png",
    }


def test_execution_and_filesystem_tools_execute_real_operations(tmp_path: Path):
    asyncio.run(_test_execution_and_filesystem_tools_execute_real_operations(tmp_path))


async def _test_execution_and_filesystem_tools_execute_real_operations(tmp_path: Path):
    sandbox = SandboxManager(
        policy=SandboxPolicy(
            allowed_paths=[tmp_path],
            command_allowlist=["echo"],
            timeout=10.0,
        )
    )
    registry = ToolRegistry()
    registry.register(create_run_command_tool(sandbox))
    registry.register(create_append_file_tool(tmp_path))
    registry.register(create_replace_in_file_tool(tmp_path))

    command = "echo hello-agentorch"
    run_result = await registry.execute("run_command", {"command": command, "workdir": str(tmp_path)})
    assert run_result.success is True
    assert run_result.data["exit_code"] == 0
    assert "hello-agentorch" in run_result.data["stdout"]
    assert run_result.data["stdout_truncated"] is False

    file_path = tmp_path / "notes.txt"
    file_path.write_text("alpha", encoding="utf-8")
    append_result = await registry.execute(
        "append_file",
        {"path": "notes.txt", "content": "beta", "ensure_newline": True},
    )
    assert append_result.data["appended_characters"] == len("\nbeta")
    assert file_path.read_text(encoding="utf-8") == "alpha\nbeta"

    replace_result = await registry.execute(
        "replace_in_file",
        {"path": "notes.txt", "old_text": "beta", "new_text": "gamma", "expected_replacements": 1},
    )
    assert replace_result.data["replacement_count"] == 1
    assert file_path.read_text(encoding="utf-8") == "alpha\ngamma"


def test_git_tools_report_status_and_diff_summary(tmp_path: Path):
    asyncio.run(_test_git_tools_report_status_and_diff_summary(tmp_path))


async def _test_git_tools_report_status_and_diff_summary(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("line-one\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.name=AgentOrch", "-c", "user.email=agentorch@example.com", "commit", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    tracked.write_text("line-one\nline-two\n", encoding="utf-8")

    registry = ToolRegistry()
    registry.register(create_git_status_tool(tmp_path))
    registry.register(create_git_diff_summary_tool(tmp_path))
    registry.register(create_git_recent_commits_tool(tmp_path))

    status = await registry.execute("git_status", {})
    assert status.success is True
    assert any("tracked.txt" in entry for entry in status.data["entries"])
    assert status.data["clean"] is False
    assert status.data["branch"]

    diff = await registry.execute("git_diff_summary", {})
    assert diff.success is True
    assert diff.data["summary"]
    assert "tracked.txt" in "\n".join(diff.data["lines"])

    recent = await registry.execute("git_recent_commits", {"limit": 1})
    assert recent.success is True
    assert recent.data["commits"][0]["subject"] == "init"


@pytest.mark.skipif(not os.getenv("AGENTORCH_RUN_LIVE_API_TESTS"), reason="Live API smoke test is opt-in.")
def test_openai_model_live_api_smoke():
    asyncio.run(_test_openai_model_live_api_smoke())


async def _test_openai_model_live_api_smoke():
    model = OpenAIModel(model="gpt-4.1-mini")
    request = ModelRequest(
        messages=[Message(role="user", content="Reply with exactly the word: pong")],
        max_tokens=8,
        temperature=0,
    )
    response = await model.generate(request)

    assert response.content.strip()
    assert "pong" in response.content.lower()


def test_openai_model_from_config_keeps_vision_model():
    model = OpenAIModel.from_config({"model": "gpt-4.1-mini", "vision_model": "gpt-4.1-vision", "api_key": "test-key"})

    assert model.config.model == "gpt-4.1-mini"
    assert model.config.vision_model == "gpt-4.1-vision"
