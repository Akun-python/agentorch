from __future__ import annotations

import importlib
import os
from time import perf_counter

from ..core.schemas import ExperimentCase, RetrievalResult
from .base import OfficialBaselineProbe, build_capsule_metadata, build_official_result, build_scope_id, format_capsule_text


class ZepOfficialAdapter:
    method = "zep_memory"

    def __init__(self, *, seed: int) -> None:
        self.seed = seed

    def probe(self) -> OfficialBaselineProbe:
        api_key = (os.getenv("ZEP_API_KEY") or "").strip()
        if not api_key:
            return OfficialBaselineProbe(enabled=False, ready=False, reason="ZEP_API_KEY 未配置。")
        try:
            self._load_sdk()
        except ImportError as exc:
            return OfficialBaselineProbe(enabled=True, ready=False, reason=f"zep_cloud 未安装：{exc}")
        return OfficialBaselineProbe(enabled=True, ready=True)

    def run(self, case: ExperimentCase, *, variant: str, max_nodes: int) -> RetrievalResult:
        zep_module, types_module = self._load_sdk()
        client = zep_module.Zep(
            api_key=(os.getenv("ZEP_API_KEY") or "").strip(),
            base_url=(os.getenv("ZEP_BASE_URL") or "").strip() or None,
        )
        scope_id = build_scope_id(case=case, method=self.method, seed=self.seed, prefix="ltmg-zep")
        episodes = [
            types_module.EpisodeData(
                data=format_capsule_text(capsule),
                type="text",
                created_at=capsule.created_at.isoformat(),
                metadata=build_capsule_metadata(capsule),
            )
            for capsule in case.capsules
        ]
        if episodes:
            client.graph.add_batch(episodes=episodes, user_id=scope_id)

        start = perf_counter()
        response = client.graph.search(
            query=case.query,
            user_id=scope_id,
            limit=max_nodes,
            scope="episodes",
        )
        latency_ms = (perf_counter() - start) * 1000
        hits = _parse_zep_hits(response)
        return build_official_result(
            method=self.method,
            variant=variant,
            summary_prefix="Zep 官方 SDK 检索结果：",
            hits=hits,
            latency_ms=latency_ms,
        )

    def _load_sdk(self):
        zep_module = importlib.import_module("zep_cloud")
        types_module = importlib.import_module("zep_cloud.types")
        return zep_module, types_module


def _parse_zep_hits(response) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for episode in getattr(response, "episodes", None) or []:
        metadata = getattr(episode, "metadata", None) or {}
        capsule_id = metadata.get("capsule_id") or getattr(episode, "uuid_", None)
        if not capsule_id:
            continue
        rows.append(
            {
                "capsule_id": capsule_id,
                "text": getattr(episode, "content", "") or metadata.get("summary") or "",
                "score": getattr(episode, "score", None),
            }
        )
    return rows
