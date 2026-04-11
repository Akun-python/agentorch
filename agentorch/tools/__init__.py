"""Structured tool definitions, registration, and decorators.

Tools are the framework's atomic external actions. This package exposes the
base tool contracts, structured results and errors, and the registration API.
"""

from .base import BaseTool, ToolError, ToolResult
from .bundles import register_default_agent_tools
from .coding import register_coding_tools
from .execution import RunCommandInput, create_run_command_tool, register_execution_tools
from .filesystem import (
    AppendFileInput,
    FindFilesInput,
    GetFileInfoInput,
    ListDirectoryInput,
    MakeDirectoryInput,
    ReadFileInput,
    ReplaceInFileInput,
    SearchTextInput,
    WriteFileInput,
    create_append_file_tool,
    create_find_files_tool,
    create_get_file_info_tool,
    create_list_directory_tool,
    create_make_directory_tool,
    create_read_file_tool,
    create_replace_in_file_tool,
    create_search_text_tool,
    create_write_file_tool,
    register_filesystem_tools,
)
from .git_tools import (
    GitDiffSummaryInput,
    GitRecentCommitsInput,
    GitStatusInput,
    create_git_diff_summary_tool,
    create_git_recent_commits_tool,
    create_git_status_tool,
    register_git_tools,
)
from .knowledge import (
    DeliberativeRetrieveInput,
    OpenRetrievedEvidenceInput,
    SearchKnowledgeAssetsInput,
    create_deliberative_retrieve_tool,
    create_open_retrieved_evidence_tool,
    create_search_knowledge_assets_tool,
)
from .web import BraveSearchInput, create_brave_search_tool, register_web_tools
from .code_interpreter import PythonInterpreterInput, create_python_interpreter_tool
from .decorators import tool
from .registry import ToolRegistry

__all__ = [
    "AppendFileInput",
    "BaseTool",
    "BraveSearchInput",
    "DeliberativeRetrieveInput",
    "FindFilesInput",
    "GetFileInfoInput",
    "GitDiffSummaryInput",
    "GitRecentCommitsInput",
    "GitStatusInput",
    "ListDirectoryInput",
    "MakeDirectoryInput",
    "OpenRetrievedEvidenceInput",
    "PythonInterpreterInput",
    "ReadFileInput",
    "ReplaceInFileInput",
    "RunCommandInput",
    "SearchKnowledgeAssetsInput",
    "SearchTextInput",
    "ToolError",
    "ToolRegistry",
    "ToolResult",
    "WriteFileInput",
    "create_append_file_tool",
    "create_brave_search_tool",
    "create_deliberative_retrieve_tool",
    "create_find_files_tool",
    "create_get_file_info_tool",
    "create_git_diff_summary_tool",
    "create_git_recent_commits_tool",
    "create_git_status_tool",
    "create_list_directory_tool",
    "create_make_directory_tool",
    "create_python_interpreter_tool",
    "create_read_file_tool",
    "create_open_retrieved_evidence_tool",
    "create_replace_in_file_tool",
    "create_run_command_tool",
    "create_search_knowledge_assets_tool",
    "create_search_text_tool",
    "create_write_file_tool",
    "register_default_agent_tools",
    "register_coding_tools",
    "register_execution_tools",
    "register_filesystem_tools",
    "register_git_tools",
    "register_web_tools",
    "tool",
]
