from pathlib import Path
import asyncio

import pytest

from agentorch.sandbox import SandboxManager, SandboxPolicy


def test_sandbox_executes_python(tmp_path: Path):
    asyncio.run(_test_sandbox_executes_python(tmp_path))


async def _test_sandbox_executes_python(tmp_path: Path):
    manager = SandboxManager(policy=SandboxPolicy(allowed_paths=[tmp_path], command_allowlist=["python"]))
    result = await manager.execute("python", "print('ok')", workdir=tmp_path)
    assert result.exit_code == 0
    assert "ok" in result.stdout


def test_sandbox_rejects_outside_path(tmp_path: Path):
    asyncio.run(_test_sandbox_rejects_outside_path(tmp_path))


async def _test_sandbox_rejects_outside_path(tmp_path: Path):
    manager = SandboxManager(policy=SandboxPolicy(allowed_paths=[tmp_path], command_allowlist=["python"]))
    with pytest.raises(PermissionError):
        await manager.execute("python", "print('blocked')", workdir=Path.cwd())


def test_sandbox_rejects_prefix_confusable_path(tmp_path: Path):
    confusing = tmp_path.parent / f"{tmp_path.name}-outside"
    confusing.mkdir(exist_ok=True)
    policy = SandboxPolicy(allowed_paths=[tmp_path], command_allowlist=["python"])

    with pytest.raises(PermissionError):
        policy.validate_workdir(confusing)


def test_sandbox_python_sessions_preserve_state(tmp_path: Path):
    asyncio.run(_test_sandbox_python_sessions_preserve_state(tmp_path))


async def _test_sandbox_python_sessions_preserve_state(tmp_path: Path):
    manager = SandboxManager(policy=SandboxPolicy(allowed_paths=[tmp_path], command_allowlist=["python"], timeout=10.0))
    session = await manager.create_session(workdir=tmp_path)
    first = await manager.execute("python", "value = 5\nprint(value)", workdir=tmp_path, session_id=session.session_id)
    second = await manager.execute("python", "value += 7\nprint(value)", workdir=tmp_path, session_id=session.session_id)
    await manager.reset_session(session.session_id)
    third = await manager.execute("python", "print('value' in globals())", workdir=tmp_path, session_id=session.session_id)
    await manager.close_session(session.session_id)

    assert len(manager.list_sessions()) == 0
    assert "12" in second.stdout
    assert "False" in third.stdout
