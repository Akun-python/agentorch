from __future__ import annotations

import os
from pathlib import Path


def _default_harness_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _clean_env_value(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        return ""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return value


def _parse_env_file(path: Path, *, overwrite: bool) -> None:
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        if overwrite or key not in os.environ:
            os.environ[key] = _clean_env_value(value)


def _candidate_env_paths(*, project_root: Path | None = None, env_file: str | Path | None = None) -> list[Path]:
    if env_file:
        return [Path(env_file).expanduser().resolve()]

    candidates: list[Path] = []
    if project_root is not None:
        candidates.append(project_root.resolve() / ".env")
    candidates.append(_default_harness_root() / ".env")

    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
    return unique


def load_harness_environment(
    *,
    project_root: str | Path | None = None,
    env_file: str | Path | None = None,
) -> list[Path]:
    loaded: list[Path] = []
    explicit_env_file = env_file is not None

    for path in _candidate_env_paths(
        project_root=Path(project_root).expanduser() if project_root is not None else None,
        env_file=env_file,
    ):
        if not path.exists():
            continue
        _parse_env_file(path, overwrite=explicit_env_file)
        loaded.append(path)
    return loaded
