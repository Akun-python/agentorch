import asyncio

from pydantic import BaseModel

from agentorch.config import RuntimeConfig
from agentorch.core import Message, ModelRequest, ModelResponse, StreamChunk, ToolCall, UsageInfo
from agentorch.feedback import HumanFeedbackManager
from agentorch.models.base import BaseModelAdapter
from agentorch.observability import SQLiteEventStore
from agentorch.runtime import Agent, Runtime
from agentorch.tools import ToolRegistry, tool
from agentorch.workflow import Node, Workflow


class ToolCallingModel(BaseModelAdapter):
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        if self.calls == 1:
            return ModelResponse(
                message=Message(
                    role="assistant",
                    content="",
                    tool_calls=[ToolCall(id="call-1", name="lookup_weather", arguments={"query": "weather"})],
                ),
                content="",
                tool_calls=[ToolCall(id="call-1", name="lookup_weather", arguments={"query": "weather"})],
                finish_reason="tool_calls",
                usage=UsageInfo(total_tokens=10),
            )
        return ModelResponse(
            message=Message(role="assistant", content="The weather is sunny."),
            content="The weather is sunny.",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=5),
        )


class StreamingModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content="unused"),
            content="unused",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )

    async def stream(self, request: ModelRequest):
        yield StreamChunk(delta_text="Hello ")
        yield StreamChunk(delta_text="observability", finish_reason="stop")


class EchoModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content="ok"),
            content="ok",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


class FailingModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        raise RuntimeError("boom")


class LookupInput(BaseModel):
    query: str


@tool(description="Return a fake weather lookup.")
async def lookup_weather(input: LookupInput):
    return {"query": input.query, "result": "sunny"}


def _observability_config(tmp_path):
    return RuntimeConfig.agent(
        observability={
            "enabled": True,
            "sqlite_path": tmp_path / "observability.db",
            "console_mode": "silent",
            "capture_todos": True,
        }
    )


def test_sqlite_event_store_updates_existing_todo(tmp_path):
    store = SQLiteEventStore(tmp_path / "events.db")
    payload = {"run_id": "run-1", "thread_id": "thread-1", "task_id": "task-1", "step_index": 0}

    store.emit("reasoning_started", payload)
    store.emit("reasoning_step_started", payload)
    store.emit("reasoning_step_completed", payload)
    store.emit("reasoning_completed", payload)

    todo_payload = store.get_run_todos("run-1")
    assert todo_payload is not None
    reasoning_items = [item for item in todo_payload["items"] if item["category"] == "reasoning"]
    assert len(reasoning_items) == 1
    assert reasoning_items[0]["progress_current"] == 1
    assert reasoning_items[0]["progress_total"] == 1
    assert reasoning_items[0]["status"] == "completed"


def test_runtime_observability_persists_events_and_tool_todos(tmp_path, capsys):
    asyncio.run(_test_runtime_observability_persists_events_and_tool_todos(tmp_path, capsys))


async def _test_runtime_observability_persists_events_and_tool_todos(tmp_path, capsys):
    tools = ToolRegistry()
    tools.register(lookup_weather)
    runtime = Runtime(model=ToolCallingModel(), tools=tools, config=_observability_config(tmp_path))

    result = await Agent(runtime=runtime).run("what is the weather", thread_id="obs-thread")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert result.reasoning_metadata["observability_enabled"] is True
    assert result.reasoning_metadata["todo_query"]["thread_id"] == "obs-thread"

    events = runtime.observability.get_run_events(result.run_id)
    event_types = [event["event_type"] for event in events]
    assert "run_started" in event_types
    assert "tool_called" in event_types
    assert "tool_result" in event_types
    assert event_types[-1] == "run_completed"

    todos = runtime.observability.get_run_todos(result.run_id)
    assert todos is not None
    tool_items = [item for item in todos["items"] if item["category"] == "tool"]
    assert len(tool_items) == 1
    assert tool_items[0]["title"] == "Tool: lookup_weather"
    assert tool_items[0]["status"] == "completed"


def test_stream_events_and_sqlite_persistence_stay_aligned(tmp_path):
    asyncio.run(_test_stream_events_and_sqlite_persistence_stay_aligned(tmp_path))


async def _test_stream_events_and_sqlite_persistence_stay_aligned(tmp_path):
    runtime = Runtime(model=StreamingModel(), config=_observability_config(tmp_path))
    agent = Agent(runtime=runtime)

    events = [event async for event in agent.run("hello", thread_id="stream-observability", stream=True)]
    final_event = events[-1]
    persisted = runtime.observability.get_run_events(final_event.run_id)

    stream_types = [event.event_type for event in events]
    persisted_types = [event["event_type"] for event in persisted]
    for event_type in {"run_started", "reasoning_started", "reasoning_completed", "run_completed"}:
        assert event_type in stream_types
        assert event_type in persisted_types
    assert stream_types.count("model_delta") == persisted_types.count("model_delta")

    todos = runtime.observability.get_run_todos(final_event.run_id)
    assert todos is not None
    reasoning_items = [item for item in todos["items"] if item["category"] == "reasoning"]
    assert len(reasoning_items) == 1


def test_waiting_human_generates_waiting_todo_and_latest_thread_lookup(tmp_path):
    asyncio.run(_test_waiting_human_generates_waiting_todo_and_latest_thread_lookup(tmp_path))


async def _test_waiting_human_generates_waiting_todo_and_latest_thread_lookup(tmp_path):
    manager = HumanFeedbackManager()
    runtime = Runtime(model=EchoModel(), human_feedback=manager, config=_observability_config(tmp_path))
    workflow = Workflow(
        entry_node="ask",
        nodes=[Node(id="ask", kind="human_input", config={"title": "Need input", "message": "Please choose"})],
        edges=[],
    )
    agent = Agent(runtime=runtime, workflow=workflow)

    result = await agent.run("start", thread_id="waiting-thread")

    assert result.status == "waiting_human"
    todos = runtime.observability.get_run_todos(result.run_id)
    assert todos is not None
    assert todos["status"] == "waiting_human"
    waiting_items = [item for item in todos["items"] if item["status"] == "waiting_human"]
    assert waiting_items
    latest = runtime.observability.get_latest_thread_todos("waiting-thread")
    assert latest is not None
    assert latest["run_id"] == result.run_id


def test_failed_run_marks_root_and_open_todos_failed(tmp_path):
    asyncio.run(_test_failed_run_marks_root_and_open_todos_failed(tmp_path))


async def _test_failed_run_marks_root_and_open_todos_failed(tmp_path):
    runtime = Runtime(model=FailingModel(), config=_observability_config(tmp_path))
    agent = Agent(runtime=runtime)

    try:
        await agent.run("fail", thread_id="failed-thread")
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:  # pragma: no cover
        raise AssertionError("Expected runtime error")

    runs = runtime.observability.get_thread_runs("failed-thread")
    assert len(runs) == 1
    assert runs[0]["status"] == "failed"
    todos = runtime.observability.get_latest_thread_todos("failed-thread")
    assert todos is not None
    assert todos["status"] == "failed"


def test_disabled_observability_remains_noop():
    runtime = Runtime(model=EchoModel(), config=RuntimeConfig.agent())

    assert runtime.observability.enabled is False
    assert runtime.observability.get_thread_runs("missing-thread") == []
