from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol

from agentorch.core import Message, ModelRequest
from agentorch.models import create_model_adapter
from agentorch.parsing import JSONParser, ParseError

from ..api.config import GraphMemoryConfig
from .entities import MemoryCapsuleDetail, SubgraphEdge
from .utils import run_async, truncate_text


SUMMARY_PROMPT = """\
你是长期记忆图谱召回结果的压缩器。你的任务不是泛泛总结，而是为后续问答保留可直接作答的关键证据。

要求：
1. 只基于给定节点和关系链压缩，不允许补充外部知识。
2. 优先保留可回答问题所需的明确事实、时间顺序、状态更新、修订关系和冲突关系。
3. 如果问题涉及 Temporal 或 Multi-hop，必须优先保留时间锚点、前后变化和证据链。
4. 每条证据尽量引用节点编号，必要时引用关系链。
5. 不要写空泛主题概括，不要只复述节点标题。
6. 输出 JSON，对象字段固定为：
{
  "summary": "string"
}
"""


class SubgraphSummarizer(Protocol):
    """统一摘要器接口，便于模板版与 LLM 版互换。"""

    def summarize(
        self,
        *,
        query: str,
        nodes: Iterable[MemoryCapsuleDetail],
        edges: list[SubgraphEdge],
        scores: dict[str, float],
        suppressed_stale_nodes: list[str],
        suppressed_conflict_nodes: list[str],
    ) -> str: ...


@dataclass(frozen=True)
class SummaryModelMetrics:
    """记录 LLM 摘要调用成本，便于后续写日志。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    duration_ms: float = 0.0


class LLMSubgraphSummarizer:
    """用轻量 flash 模型压缩召回子图，保留更可作答的证据。"""

    def __init__(self, *, config: GraphMemoryConfig, env_file: str | None) -> None:
        self.config = config
        self._parser = JSONParser()
        # 延迟导入，避免 domain -> core -> api.plugin 的循环依赖。
        from ..core.env_config import build_live_model_config

        self._model_config, self.env_report = build_live_model_config(
            model_backend=config.summary_model_backend or "",
            model_name=config.summary_model,
            env_file=env_file,
            load_env=config.summary_load_env,
            role_prefix="SUMMARY",
            overwrite_env=config.summary_overwrite_env,
        )
        self.last_metrics = SummaryModelMetrics()

    def summarize(
        self,
        *,
        query: str,
        nodes: Iterable[MemoryCapsuleDetail],
        edges: list[SubgraphEdge],
        scores: dict[str, float],
        suppressed_stale_nodes: list[str],
        suppressed_conflict_nodes: list[str],
    ) -> str:
        node_list = list(nodes)
        if not node_list:
            return "No long-term memory capsules were returned."
        payload = {
            "query": query,
            "nodes": [self._node_payload(item, scores=scores) for item in node_list],
            "edges": [self._edge_payload(item) for item in edges],
            "suppressed_stale_nodes": suppressed_stale_nodes,
            "suppressed_conflict_nodes": suppressed_conflict_nodes,
        }
        request = ModelRequest(
            messages=[
                Message(role="system", content="你只输出可解析 JSON，不添加 Markdown。"),
                Message(role="user", content=SUMMARY_PROMPT + "\n\nSUBGRAPH_JSON=" + json.dumps(payload, ensure_ascii=False, sort_keys=True)),
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=self.config.summary_max_tokens,
        )
        start = perf_counter()
        adapter = create_model_adapter(self._model_config)
        response = self._run_model(adapter, request)
        self.last_metrics = SummaryModelMetrics(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            duration_ms=(perf_counter() - start) * 1000,
        )
        return self._parse_summary(response.content, fallback_nodes=node_list, fallback_edges=edges, query=query)

    def _parse_summary(
        self,
        text: str,
        *,
        fallback_nodes: list[MemoryCapsuleDetail],
        fallback_edges: list[SubgraphEdge],
        query: str,
    ) -> str:
        try:
            parsed = self._parser.parse_sync(text)
        except (ParseError, RuntimeError):
            return self._fallback_summary(fallback_nodes, fallback_edges, query=query)
        if not isinstance(parsed, dict):
            return self._fallback_summary(fallback_nodes, fallback_edges, query=query)
        summary = " ".join(str(parsed.get("summary", "")).split()).strip()
        if summary:
            return summary
        return self._fallback_summary(fallback_nodes, fallback_edges, query=query)

    def _node_payload(self, node: MemoryCapsuleDetail, *, scores: dict[str, float]) -> dict[str, Any]:
        return {
            "capsule_id": node.capsule_id,
            "title": truncate_text(node.title, max_chars=120),
            "goal": truncate_text(node.goal, max_chars=240),
            "summary": truncate_text(node.summary, max_chars=480),
            "outcome": truncate_text(node.outcome, max_chars=1600),
            "claims": [item.model_dump() for item in node.claims[:8]],
            "entities": list(node.entities[:12]),
            "knowledge_scope": list(node.knowledge_scope[:8]),
            "tags": list(node.tags[:12]),
            "score": round(float(scores.get(node.capsule_id, node.confidence)), 4),
            "confidence": round(float(node.confidence), 4),
            "created_at": node.created_at.isoformat(),
            "status": node.status,
        }

    def _edge_payload(self, edge: SubgraphEdge) -> dict[str, Any]:
        return {
            "source_capsule_id": edge.source_capsule_id,
            "source_title": edge.source_title,
            "relation_type": edge.relation_type,
            "target_capsule_id": edge.target_capsule_id,
            "target_title": edge.target_title,
            "score": round(float(edge.score), 4),
            "support_count": edge.support_count,
        }

    def _fallback_summary(self, nodes: list[MemoryCapsuleDetail], edges: list[SubgraphEdge], *, query: str) -> str:
        lines = [f"Query focus: {truncate_text(query, max_chars=160)}", "Evidence capsules:"]
        for node in nodes[:4]:
            body = node.outcome or node.summary or node.goal or node.title
            lines.append(f"- {truncate_text(node.title, max_chars=80)}: {truncate_text(body, max_chars=260)}")
        if edges:
            lines.append("Evidence chains:")
            for edge in edges[:4]:
                lines.append(
                    "- "
                    + f"{edge.source_title or edge.source_capsule_id} "
                    + f"--{edge.relation_type}--> "
                    + f"{edge.target_title or edge.target_capsule_id}"
                )
        return "\n".join(lines)

    def _run_model(self, adapter, request: ModelRequest):
        async def _generate_and_close():
            try:
                return await adapter.generate(request)
            finally:
                await self._aclose_model_adapter(adapter)

        return run_async(_generate_and_close())

    async def _aclose_model_adapter(self, adapter) -> None:
        async_close = getattr(adapter, "aclose", None)
        if callable(async_close):
            await async_close()
            return
        close_fn = getattr(adapter, "close", None)
        if callable(close_fn):
            close_fn()


__all__ = ["LLMSubgraphSummarizer", "SubgraphSummarizer", "SummaryModelMetrics"]
