import asyncio
import contextlib
import importlib.util
import io
import logging
import uuid
from pathlib import Path

import pytest

from agentorch.core import Message, ModelRequest, ModelResponse, ToolCall, UsageInfo
from agentorch.models.base import BaseModelAdapter


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = ROOT / "examples"
ELEPHANT_DEMO = ROOT / "experiments" / "elephant_context" / "demo.py"


def _load_example_module(filename: str):
    path = EXAMPLES_DIR / filename
    module_name = f"test_example_{path.stem}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_module_from_path(path: Path):
    module_name = f"test_example_{path.stem}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExampleFakeModel(BaseModelAdapter):
    def __init__(self, *args, **kwargs) -> None:
        self.calls = 0

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        tool_names = {
            tool.get("function", {}).get("name")
            for tool in request.tools
            if isinstance(tool, dict)
        }
        latest_user = next((message.content for message in reversed(request.messages) if message.role == "user"), "")
        latest_tool = next((message.content for message in reversed(request.messages) if message.role == "tool"), "")
        system_prompt = next((message.content for message in request.messages if message.role == "system"), "")

        if latest_tool:
            content = f"Example smoke response after tool execution: {latest_tool[:120]}"
            return ModelResponse(
                message=Message(role="assistant", content=content),
                content=content,
                finish_reason="stop",
                usage=UsageInfo(total_tokens=1),
            )

        if "python_interpreter" in tool_names:
            tool_call = ToolCall(
                id="call-python-1",
                name="python_interpreter",
                arguments={
                    "code": (
                        "values = [0, 1]\n"
                        "for _ in range(8):\n"
                        "    values.append(values[-1] + values[-2])\n"
                        "print(values[:10])"
                    ),
                    "workdir": str(Path.cwd()),
                },
            )
            return ModelResponse(
                message=Message(role="assistant", content="", tool_calls=[tool_call]),
                content="",
                tool_calls=[tool_call],
                finish_reason="tool_calls",
                usage=UsageInfo(total_tokens=1),
            )

        focus = latest_user or system_prompt or "example"
        content = f"Example smoke response: {focus[:120]}"
        return ModelResponse(
            message=Message(role="assistant", content=content),
            content=content,
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


async def _run_example_main(module, **kwargs) -> str:
    buffer = io.StringIO()
    agentorch_logger = logging.getLogger("agentorch")
    previous_disabled = agentorch_logger.disabled
    agentorch_logger.disabled = True
    try:
        with contextlib.redirect_stdout(buffer):
            await module.main(**kwargs)
    finally:
        agentorch_logger.disabled = previous_disabled
    output = buffer.getvalue().strip()
    assert output
    return output


@pytest.mark.parametrize(
    "filename",
    [
        "basic_agent.py",
        "code_interpreter_agent.py",
        "rag_ready_runtime.py",
        "rag_mode_comparison.py",
        "supervisor_agents.py",
        "workflow_multi_agent_graph.py",
        "workflow_selectable_rag.py",
        "rag_scoped_multi_agent.py",
        "reasoning_cot.py",
        "reasoning_plan_execute.py",
        "reasoning_reflexion.py",
        "reasoning_tot.py",
    ],
)
def test_openai_backed_examples_run_with_fake_model(monkeypatch: pytest.MonkeyPatch, filename: str):
    asyncio.run(_test_openai_backed_examples_run_with_fake_model(monkeypatch, filename))


async def _test_openai_backed_examples_run_with_fake_model(monkeypatch: pytest.MonkeyPatch, filename: str):
    module = _load_example_module(filename)
    monkeypatch.setattr(module, "OpenAIModel", ExampleFakeModel)

    output = await _run_example_main(module)

    assert "Example smoke response" in output


@pytest.mark.parametrize(
    "filename, expected_fragment",
    [
        ("code_interpreter_session_workflow.py", "Code Interpreter Session Workflow"),
        ("evolution_facade_demo.py", "Facade Evolution Demo"),
        ("evolution_demo.py", "Best Genome"),
        ("evolution_multi_mechanism.py", "=== genetic ==="),
        ("evolution_orchestration_search.py", "Best Orchestration Genome"),
        ("evolution_workflow_demo.py", "Evolution Workflow Demo"),
    ],
)
def test_local_examples_run_end_to_end(filename: str, expected_fragment: str):
    asyncio.run(_test_local_examples_run_end_to_end(filename, expected_fragment))


async def _test_local_examples_run_end_to_end(filename: str, expected_fragment: str):
    module = _load_example_module(filename)

    output = await _run_example_main(module)

    assert expected_fragment in output


def test_elephant_plugin_demo_runs_end_to_end():
    asyncio.run(_test_elephant_plugin_demo_runs_end_to_end())


async def _test_elephant_plugin_demo_runs_end_to_end():
    module = _load_module_from_path(ELEPHANT_DEMO)
    output = await _run_example_main(module)
    assert "Elephant Plugin Output Preview" in output
