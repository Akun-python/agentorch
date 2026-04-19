from __future__ import annotations

from pathlib import Path


_WRAPPER_ROOT = Path(__file__).resolve().parent
_SRC_PACKAGE = _WRAPPER_ROOT / "src" / "codexharness"
_SRC_INIT = _SRC_PACKAGE / "__init__.py"

if not _SRC_INIT.exists():
    raise ImportError(f"Could not locate the codexharness source package at {_SRC_INIT}")

# Point package imports at the real implementation under src/codexharness.
__path__ = [str(_SRC_PACKAGE)]
__file__ = str(_SRC_INIT)

exec(compile(_SRC_INIT.read_text(encoding="utf-8"), __file__, "exec"), globals(), globals())
