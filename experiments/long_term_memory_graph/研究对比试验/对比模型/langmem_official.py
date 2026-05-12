from __future__ import annotations

import importlib
import os
from time import perf_counter

from ...core.schemas import ExperimentCase, RetrievalResult
from .base import OfficialBaselineProbe, build_capsule_metadata, build_official_result, build_scope_id, format_capsule_text


class LangMemOfficialAdapter:
    method = "langmem_memory"

    def __init__(self, *, seed: int) -> None:
        self.seed = seed

    def probe(self) -> OfficialBaselineProbe:
        api_key = _first_env("OPENAI_API_KEY", "API_KEY", "api_key")
        if not api_key:
            return OfficialBaselineProbe(enabled=False, ready=False, reason="LangMem 需要 OPENAI_API_KEY 或兼容别名。")
        try:
            self._load_sdk()
        except ImportError as exc:
            return OfficialBaselineProbe(enabled=True, ready=False, reason=f"langmem 或 langgraph 未安装：{exc}")
        return OfficialBaselineProbe(enabled=True, ready=True)

    def run(self, case: ExperimentCase, *, variant: str, max_nodes: int) -> RetrievalResult:
        langmem_module, memory_module = self._load_sdk()
        namespace = ("memories", build_scope_id(case=case, method=self.method, seed=self.seed, prefix="ltmg-langmem"))
        store = memory_module.InMemoryStore(
            index={
                "dims": _embedding_dimensions(),
                "embed": _embedding_spec(),
            }
        )
        search_tool = langmem_module.create_search_memory_tool(
            namespace=namespace,
            store=store,
            response_format="content_and_artifact",
        )
        for capsule in case.capsules:
            store.put(
                namespace,
                key=capsule.capsule_id,
                value=_build_langmem_value(capsule),
                index=["content"],
            )

        start = perf_counter()
        response = search_tool.invoke({"query": case.query, "limit": max_nodes})
        latency_ms = (perf_counter() - start) * 1000
        hits = _parse_langmem_hits(response)
        return build_official_result(
            method=self.method,
            variant=variant,
            summary_prefix="LangMem 官方检索结果：",
            hits=hits,
            latency_ms=latency_ms,
        )

    def _load_sdk(self):
        langmem_module = importlib.import_module("langmem")
        memory_module = importlib.import_module("langgraph.store.memory")
        return langmem_module, memory_module


def _build_langmem_value(capsule) -> dict[str, object]:
    payload = build_capsule_metadata(capsule)
    payload["content"] = format_capsule_text(capsule)
    return payload


def _parse_langmem_hits(response) -> list[dict[str, object]]:
    artifacts = response[1] if isinstance(response, tuple) and len(response) > 1 else []
    rows: list[dict[str, object]] = []
    for item in artifacts or []:
        value = getattr(item, "value", {}) or {}
        capsule_id = value.get("capsule_id") or getattr(item, "key", None)
        if not capsule_id:
            continue
        rows.append(
            {
                "capsule_id": capsule_id,
                "text": value.get("content") or value.get("summary") or "",
                "score": getattr(item, "score", None),
            }
        )
    return rows


def _embedding_spec() -> str:
    embed_spec = (os.getenv("LANGMEM_EMBED_SPEC") or "").strip()
    if embed_spec:
        return embed_spec
    model = (os.getenv("LANGMEM_EMBED_MODEL") or os.getenv("OPENAI_EMBEDDING_MODEL") or "text-embedding-3-small").strip()
    return f"openai:{model}"


def _embedding_dimensions() -> int:
    raw = (os.getenv("LANGMEM_EMBEDDING_DIMENSIONS") or os.getenv("OPENAI_EMBEDDING_DIMENSIONS") or "1536").strip()
    try:
        return int(raw)
    except ValueError:
        return 1536


def _first_env(*names: str) -> str:
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""
