from __future__ import annotations

import importlib
import os
from time import perf_counter
from typing import Any

from ...core.schemas import ExperimentCase, RetrievalResult
from .base import OfficialBaselineProbe, build_capsule_metadata, build_official_result, build_scope_id, format_capsule_text


class Mem0OfficialAdapter:
    """Mem0 官方 SDK baseline adapter。"""

    method = "mem0_memory"

    def __init__(self, *, seed: int) -> None:
        self.seed = seed

    def probe(self) -> OfficialBaselineProbe:
        """检查 MEM0_API_KEY 和 mem0ai SDK 是否可用。"""

        api_key = (os.getenv("MEM0_API_KEY") or "").strip()
        if not api_key:
            return OfficialBaselineProbe(enabled=False, ready=False, reason="MEM0_API_KEY 未配置。")
        try:
            self._load_sdk()
        except ImportError as exc:
            return OfficialBaselineProbe(enabled=True, ready=False, reason=f"mem0ai 未安装：{exc}")
        return OfficialBaselineProbe(enabled=True, ready=True)

    def run(self, case: ExperimentCase, *, variant: str, max_nodes: int) -> RetrievalResult:
        """写入 case 胶囊后调用 Mem0 search。"""

        mem0_module, types_module = self._load_sdk()
        client = mem0_module.MemoryClient(
            api_key=(os.getenv("MEM0_API_KEY") or "").strip(),
            host=(os.getenv("MEM0_API_URL") or os.getenv("MEM0_BASE_URL") or "").strip() or None,
        )
        add_options_cls = types_module.AddMemoryOptions
        delete_options_cls = types_module.DeleteAllMemoryOptions
        search_options_cls = types_module.SearchMemoryOptions
        filters = {"user_id": build_scope_id(case=case, method=self.method, seed=self.seed, prefix="ltmg-mem0")}

        try:
            client.delete_all(options=delete_options_cls(filters=filters))
        except Exception:
            pass

        for capsule in case.capsules:
            client.add(
                format_capsule_text(capsule),
                options=add_options_cls(
                    filters=filters,
                    metadata=build_capsule_metadata(capsule),
                    infer=False,
                ),
            )

        start = perf_counter()
        response = client.search(
            case.query,
            options=search_options_cls(
                filters=filters,
                top_k=max_nodes,
                rerank=True,
            ),
        )
        latency_ms = (perf_counter() - start) * 1000
        hits = _parse_mem0_hits(response)
        return build_official_result(
            method=self.method,
            variant=variant,
            summary_prefix="Mem0 官方 SDK 检索结果：",
            hits=hits,
            latency_ms=latency_ms,
        )

    def _load_sdk(self):
        """延迟导入 mem0 SDK。"""

        mem0_module = importlib.import_module("mem0")
        types_module = importlib.import_module("mem0.client.types")
        return mem0_module, types_module


def _parse_mem0_hits(response: dict[str, Any]) -> list[dict[str, object]]:
    """解析 Mem0 search 返回的命中列表。"""

    rows: list[dict[str, object]] = []
    for item in response.get("results", []) or []:
        metadata = item.get("metadata") or {}
        capsule_id = metadata.get("capsule_id") or item.get("id")
        if not capsule_id:
            continue
        rows.append(
            {
                "capsule_id": capsule_id,
                "text": item.get("memory") or metadata.get("summary") or metadata.get("goal") or "",
                "score": item.get("score"),
            }
        )
    return rows
