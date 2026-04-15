from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

import agentorch
from agentorch.config import ModelConfig, ObservabilityConfig, RuntimeConfig, initialize_environment
from agentorch.models.base import BaseModelAdapter
from agentorch.observability import SQLiteEventStore
from agentorch.runtime import Agent, Runtime
from agentorch.sandbox import SandboxManager, SandboxPolicy
from agentorch.security import PayloadBudgetConfig, RedactionConfig


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


def test_create_multi_agent_reuses_member_model_by_default() -> None:
    member = agentorch.create_agent(model=DummyModel(), name="worker-one")
    system = agentorch.create_multi_agent(agents=[member], name="team-one")

    assert system.export_blueprint()["kind"] == "multi_agent"
    assert system.runtime.model is member.runtime.model

    system.close()
