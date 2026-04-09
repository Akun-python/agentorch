"""Structured tool definitions, registration, and decorators.

Tools are the framework's atomic external actions. This package exposes the
base tool contracts, structured results and errors, and the registration API.
"""

from .base import BaseTool, ToolError, ToolResult
from .code_interpreter import PythonInterpreterInput, create_python_interpreter_tool
from .decorators import tool
from .registry import ToolRegistry

__all__ = [
    "BaseTool",
    "PythonInterpreterInput",
    "ToolError",
    "ToolRegistry",
    "ToolResult",
    "create_python_interpreter_tool",
    "tool",
]
