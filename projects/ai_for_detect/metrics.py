from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RewriteMetrics:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    first_token_latency_seconds: float = 0.0
    total_latency_seconds: float = 0.0
    finish_reason: str = ""


@dataclass(slots=True)
class RewriteResult:
    text: str
    model_name: str
    metrics: RewriteMetrics
