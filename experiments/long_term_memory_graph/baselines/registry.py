from __future__ import annotations

from ..core.schemas import ExperimentCase, RetrievalResult
from .base import OfficialBaselineProbe
from .langmem_official import LangMemOfficialAdapter
from .mem0_official import Mem0OfficialAdapter
from .zep_official import ZepOfficialAdapter


class OfficialBaselineRegistry:
    def __init__(self, *, seed: int) -> None:
        self.seed = seed
        self._adapters = {
            "langmem_memory": LangMemOfficialAdapter(seed=seed),
            "mem0_memory": Mem0OfficialAdapter(seed=seed),
            "zep_memory": ZepOfficialAdapter(seed=seed),
        }

    def probe(self, method: str) -> OfficialBaselineProbe:
        adapter = self._adapters.get(method)
        if adapter is None:
            return OfficialBaselineProbe(enabled=False, ready=False, reason="该方法没有官方 adapter。")
        return adapter.probe()

    def maybe_run(
        self,
        case: ExperimentCase,
        *,
        method: str,
        variant: str,
        max_nodes: int,
    ) -> RetrievalResult | None:
        adapter = self._adapters.get(method)
        if adapter is None:
            return None
        probe = adapter.probe()
        if probe.enabled and not probe.ready:
            raise RuntimeError(f"{method} 官方 baseline 处于启用态但不可用：{probe.reason}")
        if not probe.ready:
            return None
        return adapter.run(case, variant=variant, max_nodes=max_nodes)
