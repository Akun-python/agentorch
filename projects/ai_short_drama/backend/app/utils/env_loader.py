from __future__ import annotations

import os
from pathlib import Path


def _strip_wrapped_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parse_env_line(line: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text or text.startswith("#") or "=" not in text:
        return None

    if text.startswith("export "):
        text = text[7:].lstrip()

    key, value = text.split("=", 1)
    key = key.strip()
    value = _strip_wrapped_quotes(value.strip())
    if not key:
        return None
    return key, value


def _load_env_file(env_path: Path, *, override: bool = False) -> None:
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        parsed = _parse_env_line(raw_line)
        if not parsed:
            continue
        key, value = parsed
        if override or key not in os.environ:
            os.environ[key] = value


def load_project_env(project_root: Path, *, override: bool = False) -> list[Path]:
    """按候选路径加载 .env，优先支持项目外层和 api 调用示例目录。"""
    root = Path(project_root).resolve()
    env_paths: list[Path] = []

    explicit_path = os.getenv("AI_SHORT_DRAMA_ENV_PATH")
    if explicit_path:
        env_paths.append(Path(explicit_path).expanduser())

    env_paths.append(root / ".env")
    env_paths.append(root.parent.parent / ".env")
    env_paths.append(root / "api调用指南" / ".env")

    loaded: list[Path] = []
    seen: set[Path] = set()
    for path in env_paths:
        resolved = path.resolve()
        if resolved in seen or not resolved.exists():
            continue
        _load_env_file(resolved, override=override)
        loaded.append(resolved)
        seen.add(resolved)
    return loaded


def get_first_env(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def parse_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default
