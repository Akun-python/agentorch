from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator

from ..api.models import MemoryCapsuleCandidate
from .utils import ensure_utc_datetime, normalize_text


class MemoryCapsuleDetail(MemoryCapsuleCandidate):
    scene_hash: str | None = None
    reuse_count: int = 0
    last_validated_at: datetime | None = None
    summary_embedding: list[float] | None = None

    @field_validator("last_validated_at", mode="before")
    @classmethod
    def _normalize_last_validated_at(cls, value: Any) -> datetime | None:
        if value in (None, ""):
            return None
        return ensure_utc_datetime(value)


class GraphEdgeCandidate(BaseModel):
    source_capsule_id: str
    relation_type: str
    target_capsule_id: str
    score: float = 0.0
    created_at: datetime
    source_rule: str
    support_count: int = 1

    @field_validator("source_capsule_id", "relation_type", "target_capsule_id", "source_rule", mode="before")
    @classmethod
    def _normalize_textual_fields(cls, value: Any) -> str:
        return normalize_text(value)

    @field_validator("created_at", mode="before")
    @classmethod
    def _normalize_created_at(cls, value: Any) -> datetime:
        return ensure_utc_datetime(value)


@dataclass(frozen=True)
class SearchHit:
    node: MemoryCapsuleDetail
    score: float


@dataclass(frozen=True)
class SubgraphEdge:
    source_capsule_id: str
    target_capsule_id: str
    relation_type: str
    score: float = 0.0
    source_rule: str = ""
    support_count: int = 1
    source_title: str = ""
    target_title: str = ""
