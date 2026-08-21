from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from .entities import MemoryCapsuleDetail, SubgraphEdge
from .summary_llm import SubgraphSummarizer
from .utils import truncate_text


class TemplateSubgraphSummarizer(SubgraphSummarizer):
    """把召回子图压缩成可喂给 Agent 的短摘要。"""

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
        """按节点、关系链和风险提示组织摘要。"""

        node_list = list(nodes)
        if not node_list:
            return "No long-term memory capsules were returned."

        ranked = sorted(node_list, key=lambda item: scores.get(item.capsule_id, item.confidence), reverse=True)
        dominant_terms = self._dominant_terms(ranked)
        lines = [
            f"Subgraph theme: {dominant_terms or truncate_text(query or 'general prior experience', max_chars=120)}.",
            "High-value capsules:",
        ]
        for node in ranked[:3]:
            lines.append(f"- {truncate_text(node.title, max_chars=80)}: {truncate_text(node.summary or node.outcome, max_chars=180)}")
        if edges:
            lines.append("Key relation chains:")
            for edge in sorted(edges, key=lambda item: item.score, reverse=True)[:4]:
                lines.append(
                    "- "
                    + f"{edge.source_title or edge.source_capsule_id} "
                    + f"--{edge.relation_type}--> "
                    + f"{edge.target_title or edge.target_capsule_id}"
                )
        risks: list[str] = []
        if suppressed_stale_nodes:
            risks.append(f"stale nodes suppressed: {', '.join(suppressed_stale_nodes[:4])}")
        if suppressed_conflict_nodes:
            risks.append(f"conflicting nodes suppressed: {', '.join(suppressed_conflict_nodes[:4])}")
        if risks:
            lines.append("Conflict and risk notes:")
            for item in risks:
                lines.append(f"- {item}")
        return "\n".join(lines)

    def _dominant_terms(self, nodes: list[MemoryCapsuleDetail]) -> str:
        """从标签、实体和知识范围中提取主题词。"""

        counter: Counter[str] = Counter()
        for node in nodes[:6]:
            for value in node.tags + node.entities + node.knowledge_scope:
                if value:
                    counter[value] += 1
        if not counter:
            return truncate_text(nodes[0].goal or nodes[0].summary, max_chars=120)
        return ", ".join(term for term, _ in counter.most_common(4))
