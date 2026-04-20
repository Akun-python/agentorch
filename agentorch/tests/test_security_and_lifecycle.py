from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

import agentorch
from agentorch.config import ModelConfig, ObservabilityConfig, RuntimeConfig, initialize_environment
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.models.base import BaseModelAdapter
from agentorch.observability import SQLiteEventStore
from agentorch.runtime import Agent, Runtime
from agentorch.sandbox import SandboxManager, SandboxPolicy
from agentorch.security import PayloadBudgetConfig, RedactionConfig
from agentorch.tools import ToolRegistry, create_python_interpreter_tool


class DummyModel(BaseModelAdapter):
    def __init__(self) -> None:
        self.config = ModelConfig(
            model="dummy-model",
            api_key="sk-secret-test-key-1234567890",
            base_url="https://example.test/v1",
        )
        self.closed = False

    async def generate(self, request):  # pragma: no cover
        raise RuntimeError("not used in these tests")

    async def aclose(self) -> None:
        self.closed = True


class ReplyModel(DummyModel):
    def __init__(self, reply: str = "ok") -> None:
        super().__init__()
        self.reply = reply

    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content=self.reply),
            content=self.reply,
            finish_reason="stop",
            usage=UsageInfo(total_tokens=4),
        )


class RecordingAgent(Agent):
    def __init__(self, *, runtime: Runtime) -> None:
        super().__init__(runtime=runtime)
        self.calls: list[dict[str, object]] = []

    def run(
        self,
        user_input: str,
        *,
        thread_id: str,
        metadata: dict[str, object] | None = None,
        stream: bool = False,
    ):
        self.calls.append(
            {
                "user_input": user_input,
                "thread_id": thread_id,
                "metadata": dict(metadata or {}),
                "memory": self.runtime.memory,
                "knowledge_base": self.runtime.knowledge_base,
                "retriever": self.runtime.retriever,
            }
        )
        return super().run(user_input, thread_id=thread_id, metadata=metadata, stream=stream)


def test_agent_exports_redact_secrets() -> None:
    runtime = Runtime(model=DummyModel(), config=RuntimeConfig())
    agent = Agent(runtime=runtime)

    exported = agent.export_core_assembly()
    serialized = str(exported)

    assert "sk-secret-test-key" not in serialized
    assert "[REDACTED]" in serialized
    assert exported["redaction_applied"] is True
    assert exported["resource_state"]["closed"] is False


def test_observability_store_redacts_and_shapes_payload(tmp_path: Path) -> None:
    store = SQLiteEventStore(
        tmp_path / "observability.db",
        redaction=RedactionConfig(),
        payload_budget=PayloadBudgetConfig(max_total_chars=300, max_string_chars=60, max_collection_items=2),
    )

    store.emit(
        "human_feedback_emitted",
        {
            "run_id": "run-1",
            "thread_id": "thread-1",
            "message": "token sk-secret-test-key-1234567890 should not be persisted",
            "metadata": {"api_key": "plain-secret", "items": list(range(20))},
        },
    )

    events = store.get_run_events("run-1")
    assert len(events) == 1
    payload = events[0]
    serialized = str(payload)

    assert "plain-secret" not in serialized
    assert "sk-secret-test-key" not in serialized
    assert payload.get("redaction_applied") is True or payload.get("full_payload_available") is False


def test_runtime_and_agent_aclose_close_model() -> None:
    model = DummyModel()
    runtime = Runtime(model=model, config=RuntimeConfig())
    agent = Agent(runtime=runtime)

    asyncio.run(agent.aclose())

    assert model.closed is True
    assert runtime._closed is True


def test_runtime_aclose_closes_persistent_python_sessions(tmp_path: Path) -> None:
    asyncio.run(_test_runtime_aclose_closes_persistent_python_sessions(tmp_path))


async def _test_runtime_aclose_closes_persistent_python_sessions(tmp_path: Path) -> None:
    sandbox = SandboxManager(
        policy=SandboxPolicy(
            allowed_paths=[tmp_path],
            command_allowlist=["python"],
            timeout=10.0,
        )
    )
    tools = ToolRegistry.from_tools(create_python_interpreter_tool(sandbox))
    runtime = Runtime(model=DummyModel(), tools=tools, sandbox=sandbox, config=RuntimeConfig())

    await tools.execute("python_interpreter", {"create_session": True, "workdir": str(tmp_path)})
    assert len(sandbox.list_sessions()) == 1

    await runtime.aclose()

    assert len(sandbox.list_sessions()) == 0


def test_sandbox_blocks_shell_by_default(tmp_path: Path) -> None:
    policy = SandboxPolicy(
        allowed_paths=[tmp_path],
        command_allowlist=["powershell"],
        allow_shell=False,
    )
    manager = SandboxManager(policy=policy)

    with pytest.raises(PermissionError):
        asyncio.run(manager.execute("shell", "Write-Output hi", workdir=tmp_path, use_shell=True))


def test_sandbox_treats_shell_executor_as_real_command(tmp_path: Path) -> None:
    policy = SandboxPolicy(
        allowed_paths=[tmp_path],
        command_allowlist=["git"],
        allow_shell=True,
    )
    manager = SandboxManager(policy=policy)

    with pytest.raises(PermissionError):
        asyncio.run(manager.execute("shell", "git && powershell -Command Write-Output hi", workdir=tmp_path, use_shell=True))


def test_sandbox_allows_structured_non_shell_execution(tmp_path: Path) -> None:
    executable = str(Path(sys.executable)).lower()
    policy = SandboxPolicy(
        allowed_paths=[tmp_path],
        command_allowlist=[executable],
        allow_shell=False,
    )
    manager = SandboxManager(policy=policy)

    result = asyncio.run(manager.execute("shell", [sys.executable, "-c", "print('ok')"], workdir=tmp_path))

    assert result.exit_code == 0
    assert result.stdout.strip() == "ok"


def test_local_env_is_not_auto_loaded_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=sk-from-dotenv\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    assert ModelConfig().api_key is None

    initialize_environment()

    assert ModelConfig().api_key == "sk-from-dotenv"


def test_runtime_observability_config_has_secure_defaults() -> None:
    config = RuntimeConfig(
        observability=ObservabilityConfig(enabled=True),
    )

    assert config.observability is not None
    assert config.observability.redaction.enabled is True
    assert config.unsafe_export is False


def test_top_level_exports_include_new_security_and_env_api() -> None:
    assert hasattr(agentorch, "initialize_environment")
    assert hasattr(agentorch, "RedactionConfig")
    assert hasattr(agentorch, "PayloadBudgetConfig")
    assert hasattr(agentorch, "SandboxPolicy")
    assert hasattr(agentorch, "ExecutionRequest")
    assert hasattr(agentorch, "bootstrap_model_defaults")


def test_create_multi_agent_keeps_external_member_runtime_open_on_close() -> None:
    member = agentorch.create_agent(model=DummyModel(), name="worker-one")
    system = agentorch.create_multi_agent(agents=[member], name="team-one")

    assert system.export_blueprint()["kind"] == "multi_agent"
    assert system.runtime.model is not member.runtime.model

    system.close()

    assert member.runtime._closed is False
    assert member.runtime.model.closed is False
    member.close()


def test_create_multi_agent_role_wrapper_preserves_external_member_and_override_metadata() -> None:
    member = agentorch.create_agent(model=DummyModel(), name="worker-base")
    system = agentorch.create_multi_agent(
        roles=[
            {
                "agent": member,
                "name": "reviewer",
                "role": "paper_reviewer",
                "description": "Review specialist",
                "knowledge_scope": ["papers"],
                "capabilities": ["retrieve"],
                "tags": ["paper"],
                "metadata": {"compat_mode": True},
                "supports_parallel_tasks": True,
                "max_delegation_depth": 3,
            }
        ],
        name="team-role-wrapper",
    )

    registered = system.runtime.agent_registry.get("reviewer")
    blueprint = system.export_blueprint()

    assert registered.agent is member
    assert registered.spec.metadata["compat_mode"] is True
    assert registered.spec.supports_parallel_tasks is True
    assert registered.spec.max_delegation_depth == 3
    assert registered.spec.allowed_knowledge_scopes == ["papers"]
    assert blueprint["members"][0]["role"] == "paper_reviewer"
    assert blueprint["members"][0]["knowledge_scope"] == ["papers"]

    system.close()

    assert member.runtime._closed is False
    assert member.runtime.model.closed is False
    member.close()


def test_create_multi_agent_external_member_applies_shared_scope_and_restores_runtime() -> None:
    original_memory = agentorch.MemoryManager()
    shared_memory = agentorch.MemoryManager()
    member = RecordingAgent(runtime=Runtime(model=ReplyModel("direct-ok"), memory=original_memory, config=RuntimeConfig()))
    system = agentorch.create_multi_agent(
        agents=[member],
        shared_memory=shared_memory,
        shared_knowledge={"knowledge_scope": ["shared-scope"]},
        name="team-shared-scope",
    )

    result = system.run_sync("use the shared defaults", thread_id="team-shared-scope")

    assert "direct-ok" in result.output_text
    assert member.calls[-1]["metadata"]["knowledge_scope"] == ["shared-scope"]
    assert member.calls[-1]["memory"] is shared_memory
    assert member.runtime.memory is original_memory

    system.close()

    assert member.runtime._closed is False
    assert member.runtime.model.closed is False
    member.close()


def test_create_multi_agent_external_role_wrapper_applies_shared_runtime_dependencies_temporarily() -> None:
    original_memory = agentorch.MemoryManager()
    shared_memory = agentorch.MemoryManager()
    shared_knowledge = agentorch.InMemoryKnowledgeBase()
    member = RecordingAgent(runtime=Runtime(model=ReplyModel("wrapped-ok"), memory=original_memory, config=RuntimeConfig()))
    system = agentorch.create_multi_agent(
        roles=[
            {
                "agent": member,
                "name": "reviewer",
                "knowledge_scope": ["papers"],
            }
        ],
        shared_memory=shared_memory,
        shared_knowledge=shared_knowledge,
        name="team-shared-runtime",
    )

    result = system.run_sync("review the paper", thread_id="team-shared-runtime")

    assert "wrapped-ok" in result.output_text
    assert member.calls[-1]["metadata"]["knowledge_scope"] == ["papers"]
    assert member.calls[-1]["memory"] is shared_memory
    assert member.calls[-1]["knowledge_base"] is shared_knowledge
    assert member.calls[-1]["retriever"] is not None
    assert member.runtime.memory is original_memory
    assert member.runtime.knowledge_base is None
    assert member.runtime.retriever is None

    system.close()

    assert member.runtime._closed is False
    assert member.runtime.model.closed is False
    member.close()


def test_create_multi_agent_closes_inline_managed_member_runtimes() -> None:
    system = agentorch.create_multi_agent(
        roles=[
            {
                "name": "planner",
                "model": DummyModel(),
            }
        ],
        name="managed-team",
    )

    member = system.runtime.agent_registry.get("planner").agent

    system.close()

    assert member.runtime._closed is True
    assert member.runtime.model.closed is True
