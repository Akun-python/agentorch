import os
from pathlib import Path

from dotenv import load_dotenv


def load_env_from_script_dir(script_file: str, env_name: str = ".env") -> Path:
    """按脚本所在目录加载 .env，避免受当前工作目录影响。"""
    script_dir = Path(script_file).resolve().parent
    env_path = script_dir / env_name
    load_dotenv(dotenv_path=env_path, override=False)
    return env_path


def get_first_env(*keys: str) -> str:
    """按顺序读取第一个非空环境变量。"""
    for key in keys:
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    return ""


def parse_bool_env(key: str, default: bool = False) -> bool:
    """读取布尔环境变量，兼容常见真值写法。"""
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def resolve_from_script_dir(script_file: str, relative_path: str) -> str:
    """把相对路径解析到脚本目录下。"""
    return str(Path(script_file).resolve().parent / relative_path)
