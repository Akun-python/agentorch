from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from agentorch.core import UsageInfo


class EventBus:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append({"event_type": event_type, **payload})


class Logger:
    def __init__(self, name: str = "agentorch", file_path: str | Path | None = None) -> None:
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(console_handler)
        if file_path:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(file_path, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(file_handler)

    def log(self, event_type: str, payload: dict[str, Any]) -> None:
        self.logger.info(json.dumps({"event_type": event_type, **payload}, ensure_ascii=False))


class Tracer:
    def __init__(self, event_bus: EventBus, logger: Logger | None = None) -> None:
        self.event_bus = event_bus
        self.logger = logger

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        self.event_bus.publish(event_type, payload)
        if self.logger:
            self.logger.log(event_type, payload)


class UsageTracker:
    def __init__(self) -> None:
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

    def add(self, usage: UsageInfo) -> None:
        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens
        self.total_tokens += usage.total_tokens

    def summary(self) -> UsageInfo:
        return UsageInfo(
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            total_tokens=self.total_tokens,
        )
