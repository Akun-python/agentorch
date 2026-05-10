import os
from pathlib import Path


def _strip_wrapped_quotes(value: str) -> str:
    """去掉成对包裹的引号。"""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parse_env_line(line: str):
    """解析单行 KEY=VALUE，忽略注释和空行。"""
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


def load_env_from_script_dir(script_file: str, env_name: str = ".env", override: bool = False) -> str:
    """从脚本同目录加载 .env，避免依赖当前工作目录。"""
    env_path = Path(script_file).resolve().parent / env_name
    if not env_path.exists():
        return str(env_path)

    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        parsed = _parse_env_line(raw_line)
        if not parsed:
            continue
        key, value = parsed
        if override or key not in os.environ:
            os.environ[key] = value

    return str(env_path)


def get_first_env(*names: str, default: str | None = None) -> str | None:
    """按顺序返回第一个非空环境变量。"""
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def parse_bool_env(name: str, default: bool = False) -> bool:
    """把常见字符串环境变量解析为布尔值。"""
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default
