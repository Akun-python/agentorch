from __future__ import annotations

import sys
from datetime import datetime
from typing import TextIO


class ProgressReporter:
    def emit(
        self,
        phase: str,
        message: str,
        *,
        task_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        raise NotImplementedError


class NullProgressReporter(ProgressReporter):
    def emit(
        self,
        phase: str,
        message: str,
        *,
        task_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        return


class ConsoleProgressReporter(ProgressReporter):
    def __init__(self, *, stream: TextIO | None = None, enabled: bool = True) -> None:
        self.stream = stream or sys.stderr
        self.enabled = enabled

    def emit(
        self,
        phase: str,
        message: str,
        *,
        task_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        if not self.enabled:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        tags = [f"[{timestamp}]", "[codexharness]", phase]
        if task_id:
            tags.append(task_id)
        if session_id:
            tags.append(session_id)
        print(" ".join(tags) + f" {message}", file=self.stream, flush=True)


def shorten_text(text: str, *, limit: int = 180) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."
