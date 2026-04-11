from __future__ import annotations

from pathlib import Path

from .append_file import create_append_file_tool
from .find_files import create_find_files_tool
from .get_file_info import create_get_file_info_tool
from .list_directory import create_list_directory_tool
from .make_directory import create_make_directory_tool
from .read_file import create_read_file_tool
from .replace_in_file import create_replace_in_file_tool
from .search_text import create_search_text_tool
from .write_file import create_write_file_tool


def register_filesystem_tools(registry, workspace_root: str | Path) -> None:
    registry.register(create_list_directory_tool(workspace_root))
    registry.register(create_read_file_tool(workspace_root))
    registry.register(create_write_file_tool(workspace_root))
    registry.register(create_make_directory_tool(workspace_root))
    registry.register(create_get_file_info_tool(workspace_root))
    registry.register(create_append_file_tool(workspace_root))
    registry.register(create_replace_in_file_tool(workspace_root))
    registry.register(create_search_text_tool(workspace_root))
    registry.register(create_find_files_tool(workspace_root))
