from __future__ import annotations

import os
import tempfile
from pathlib import Path

from agentorch.tools.base import ToolError


DEFAULT_BINARY_SAMPLE_BYTES = 8192


def ensure_parent_directory(target: Path, *, make_dirs: bool, tool_name: str) -> None:
    if target.parent.exists():
        return
    if not make_dirs:
        raise ToolError(f"Parent directory '{target.parent}' does not exist.", tool_name=tool_name)
    target.parent.mkdir(parents=True, exist_ok=True)


def create_backup_file(target: Path, *, root: Path, tool_name: str, suffix: str = ".bak") -> str | None:
    if not target.exists() or not target.is_file():
        return None
    backup = target.with_name(f"{target.name}{suffix}")
    backup.write_bytes(target.read_bytes())
    return backup.relative_to(root).as_posix()


def atomic_write_text(target: Path, content: str, *, encoding: str) -> None:
    fd, temp_path = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    tmp = Path(temp_path)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            handle.write(content)
        tmp.replace(target)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def is_probably_binary(path: Path) -> bool:
    with path.open("rb") as handle:
        sample = handle.read(DEFAULT_BINARY_SAMPLE_BYTES)
    if b"\x00" in sample:
        return True
    return False


def read_text_file(target: Path, *, encoding: str, tool_name: str) -> str:
    if not target.exists():
        raise ToolError(f"File '{target}' does not exist.", tool_name=tool_name)
    if not target.is_file():
        raise ToolError(f"Path '{target}' is not a file.", tool_name=tool_name)
    if is_probably_binary(target):
        raise ToolError(f"File '{target}' appears to be binary and cannot be read as text.", tool_name=tool_name)
    try:
        return target.read_text(encoding=encoding)
    except UnicodeDecodeError as exc:
        raise ToolError(f"File '{target}' could not be decoded with encoding '{encoding}'.", tool_name=tool_name) from exc
