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
