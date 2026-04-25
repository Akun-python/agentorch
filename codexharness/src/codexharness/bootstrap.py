from __future__ import annotations

import sys
from pathlib import Path


def ensure_repo_root_on_path() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "agentorch" / "__init__.py"
        if candidate.exists():
            root = str(parent)
            if root not in sys.path:
                sys.path.insert(0, root)
            return parent
    raise RuntimeError("Could not locate the repository root containing the local 'agentorch' package.")
