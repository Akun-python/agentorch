import asyncio
from pathlib import Path

from agentorch.sandbox import SandboxManager, SandboxPolicy
from agentorch.tools import create_python_interpreter_tool


def test_python_interpreter_tool_executes_code(tmp_path: Path):
    asyncio.run(_test_python_interpreter_tool_executes_code(tmp_path))


async def _test_python_interpreter_tool_executes_code(tmp_path: Path):
    sandbox = SandboxManager(
        policy=SandboxPolicy(
            allowed_paths=[tmp_path],
            command_allowlist=["python"],
            timeout=10.0,
        )
    )
    tool = create_python_interpreter_tool(sandbox)
    result = await tool.run(tool.input_model(code="print(2 + 3)", workdir=str(tmp_path)))
    assert result.success is True
    assert result.data["exit_code"] == 0
    assert "5" in result.data["stdout"]


def test_python_interpreter_tool_executes_multiline_code(tmp_path: Path):
    asyncio.run(_test_python_interpreter_tool_executes_multiline_code(tmp_path))


async def _test_python_interpreter_tool_executes_multiline_code(tmp_path: Path):
    sandbox = SandboxManager(
        policy=SandboxPolicy(
            allowed_paths=[tmp_path],
            command_allowlist=["python"],
            timeout=10.0,
        )
    )
    tool = create_python_interpreter_tool(sandbox)
    code = "\n".join(
        [
            "values = [1, 2, 3, 4]",
            "print(sum(values))",
            "print(values[-1])",
        ]
    )
    result = await tool.run(tool.input_model(code=code, workdir=str(tmp_path)))
    assert result.success is True
    assert result.data["exit_code"] == 0
    assert "10" in result.data["stdout"]
    assert "4" in result.data["stdout"]
