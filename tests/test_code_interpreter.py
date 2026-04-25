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


def test_python_interpreter_tool_supports_persistent_sessions(tmp_path: Path):
    asyncio.run(_test_python_interpreter_tool_supports_persistent_sessions(tmp_path))


async def _test_python_interpreter_tool_supports_persistent_sessions(tmp_path: Path):
    sandbox = SandboxManager(
        policy=SandboxPolicy(
            allowed_paths=[tmp_path],
            command_allowlist=["python"],
            timeout=10.0,
        )
    )
    tool = create_python_interpreter_tool(sandbox)

    start = await tool.run(tool.input_model(create_session=True, workdir=str(tmp_path)))
    session_id = start.data["session_id"]
    assert start.success is True
    assert start.data["created"] is True

    first = await tool.run(
        tool.input_model(
            session_id=session_id,
            code="counter = 40\nprint(counter)",
            workdir=str(tmp_path),
        )
    )
    second = await tool.run(
        tool.input_model(
            session_id=session_id,
            code="counter += 2\nprint(counter)",
            workdir=str(tmp_path),
        )
    )
    reset = await tool.run(tool.input_model(session_id=session_id, reset_session=True))
    third = await tool.run(
        tool.input_model(
            session_id=session_id,
            code="print('counter' in globals())",
            workdir=str(tmp_path),
        )
    )
    closed = await tool.run(tool.input_model(session_id=session_id, close_session=True))

    assert first.data["persistent"] is True
    assert second.data["session_id"] == session_id
    assert "42" in second.data["stdout"]
    assert reset.data["reset"] is True
    assert "False" in third.data["stdout"]
    assert closed.data["closed"] is True
