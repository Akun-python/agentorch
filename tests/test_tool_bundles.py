import asyncio
from pathlib import Path

from agentorch.sandbox import SandboxManager, SandboxPolicy
from agentorch.tools import (
    ToolRegistry,
    register_coding_tools,
    register_default_agent_tools,
    register_execution_tools,
    register_filesystem_tools,
    register_git_tools,
)


def test_filesystem_execution_and_git_bundles_can_be_assigned_separately(tmp_path: Path):
    asyncio.run(_test_filesystem_execution_and_git_bundles_can_be_assigned_separately(tmp_path))


async def _test_filesystem_execution_and_git_bundles_can_be_assigned_separately(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")

    filesystem_registry = ToolRegistry()
    register_filesystem_tools(filesystem_registry, tmp_path)
    assert "read_file" in filesystem_registry
    assert "write_file" in filesystem_registry
    assert "run_command" not in filesystem_registry
    assert "git_status" not in filesystem_registry

    sandbox = SandboxManager(
        policy=SandboxPolicy(
            allowed_paths=[tmp_path],
            command_allowlist=["python", "git", "cmd", "powershell"],
            timeout=10.0,
        )
    )
    execution_registry = ToolRegistry()
    register_execution_tools(execution_registry, sandbox)
    assert "run_command" in execution_registry
    assert "read_file" not in execution_registry

    git_registry = ToolRegistry()
    register_git_tools(git_registry, Path.cwd())
    assert "git_status" in git_registry
    assert "git_diff_summary" in git_registry
    assert "git_recent_commits" in git_registry
    assert "read_file" not in git_registry


def test_register_default_agent_tools_combines_selected_bundles(tmp_path: Path):
    sandbox = SandboxManager(
        policy=SandboxPolicy(
            allowed_paths=[tmp_path],
            command_allowlist=["python", "git", "cmd", "powershell"],
            timeout=10.0,
        )
    )
    registry = ToolRegistry()
    register_default_agent_tools(registry, workspace_root=tmp_path, sandbox=sandbox)
    for tool_name in ["read_file", "run_command", "git_status"]:
        assert tool_name in registry


def test_tool_registry_with_bundles_returns_preconfigured_registry(tmp_path: Path):
    sandbox = SandboxManager(
        policy=SandboxPolicy(
            allowed_paths=[tmp_path],
            command_allowlist=["python", "git", "cmd", "powershell"],
            timeout=10.0,
        )
    )
    registry = ToolRegistry.with_bundles(workspace_root=tmp_path, sandbox=sandbox)
    assert "read_file" in registry
    assert "run_command" in registry
    assert "git_status" in registry


def test_register_web_tools_and_bundle_option_include_brave_search(tmp_path: Path):
    sandbox = SandboxManager(
        policy=SandboxPolicy(
            allowed_paths=[tmp_path],
            command_allowlist=["python", "git", "cmd", "powershell"],
            timeout=10.0,
        )
    )
    registry = ToolRegistry.with_bundles(
        workspace_root=tmp_path,
        sandbox=sandbox,
        include_web=True,
        brave_api_key="brave-test",
    )
    assert "brave_search" in registry


def test_register_coding_tools_remains_compatible_alias(tmp_path: Path):
    registry = ToolRegistry()
    register_coding_tools(registry, tmp_path)
    for tool_name in [
        "list_directory",
        "read_file",
        "write_file",
        "search_text",
        "find_files",
        "append_file",
        "replace_in_file",
        "make_directory",
        "get_file_info",
    ]:
        assert tool_name in registry
