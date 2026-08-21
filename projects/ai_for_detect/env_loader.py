from __future__ import annotations

from pathlib import Path

import agentorch

from .config import DEFAULT_ENV_PATH


def load_project_env(env_path: Path | None = None, *, overwrite: bool = False) -> Path | None:
    """加载本项目同目录下的 .env，不依赖仓库根目录环境。"""

    resolved_path = Path(env_path or DEFAULT_ENV_PATH)
    if not resolved_path.exists():
        return None
    agentorch.initialize_environment(env_path=resolved_path, overwrite=overwrite)
    return resolved_path
