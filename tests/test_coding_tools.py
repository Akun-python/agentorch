import asyncio
from pathlib import Path

import pytest

from agentorch.tools import (
    ToolRegistry,
    create_find_files_tool,
    create_get_file_info_tool,
    create_list_directory_tool,
    create_make_directory_tool,
    create_read_file_tool,
    create_replace_in_file_tool,
    create_search_text_tool,
    create_write_file_tool,
    register_coding_tools,
)
from agentorch.tools.base import ToolError


def test_coding_tools_list_read_write_search_and_find(tmp_path: Path):
    asyncio.run(_test_coding_tools_list_read_write_search_and_find(tmp_path))


async def _test_coding_tools_list_read_write_search_and_find(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hello')\nvalue = 3\n", encoding="utf-8")

    registry = ToolRegistry()
    registry.register(create_list_directory_tool(tmp_path))
    registry.register(create_read_file_tool(tmp_path))
    registry.register(create_write_file_tool(tmp_path))
    registry.register(create_search_text_tool(tmp_path))
    registry.register(create_find_files_tool(tmp_path))
    registry.register(create_make_directory_tool(tmp_path))
    registry.register(create_get_file_info_tool(tmp_path))
    registry.register(create_replace_in_file_tool(tmp_path))

    listed = await registry.execute("list_directory", {"path": "src", "include_size": True})
    assert any(item["path"] == "src/app.py" for item in listed.data["entries"])
    assert listed.data["count"] >= 1

    read = await registry.execute("read_file", {"path": "src/app.py", "include_line_numbers": True})
    assert "1: print('hello')" in read.data["content"]

    write = await registry.execute("write_file", {"path": "src/generated.txt", "content": "alpha\nbeta\n"})
    assert write.data["characters_written"] == len("alpha\nbeta\n")
    assert (tmp_path / "src" / "generated.txt").read_text(encoding="utf-8") == "alpha\nbeta\n"
    assert write.data["created"] is True

    searched = await registry.execute("search_text", {"pattern": "value", "path": "src", "glob": "*.py", "context_lines": 1})
    assert searched.data["matches"][0]["path"] == "src/app.py"
    assert searched.data["matches"][0]["line"] == 2
    assert searched.data["files_scanned"] >= 1
    assert searched.data["matches"][0]["context"]

    found = await registry.execute("find_files", {"pattern": "*.txt", "path": "src"})
    assert "src/generated.txt" in found.data["matches"]
    assert found.data["count"] >= 1

    made = await registry.execute("make_directory", {"path": "src/nested/output"})
    assert made.data["created"] is True
    assert (tmp_path / "src" / "nested" / "output").is_dir()

    info = await registry.execute("get_file_info", {"path": "src/generated.txt"})
    assert info.data["type"] == "file"
    assert info.data["size_bytes"] == len("alpha\nbeta\n".encode("utf-8"))

    replaced = await registry.execute(
        "replace_in_file",
        {"path": "src/generated.txt", "old_text": "beta", "new_text": "gamma", "dry_run": True},
    )
    assert replaced.data["dry_run"] is True
    assert (tmp_path / "src" / "generated.txt").read_text(encoding="utf-8") == "alpha\nbeta\n"


def test_coding_tools_block_paths_outside_workspace(tmp_path: Path):
    asyncio.run(_test_coding_tools_block_paths_outside_workspace(tmp_path))


async def _test_coding_tools_block_paths_outside_workspace(tmp_path: Path):
    registry = ToolRegistry()
    registry.register(create_read_file_tool(tmp_path))
    with pytest.raises(ToolError):
        await registry.execute("read_file", {"path": "../outside.txt"})


def test_register_coding_tools_adds_default_toolkit(tmp_path: Path):
    registry = ToolRegistry()
    register_coding_tools(registry, tmp_path)
    for tool_name in ["list_directory", "read_file", "write_file", "search_text", "find_files", "make_directory", "get_file_info"]:
        assert tool_name in registry
