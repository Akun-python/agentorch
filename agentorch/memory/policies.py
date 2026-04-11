from __future__ import annotations

import hashlib
import json
from typing import Any

from .base import MemoryDecayPolicy, MemoryIndexPolicy, MemoryPromotionPolicy, MemoryRecallPolicy
from .types import EpisodicCapsule, MemoryRecord


def _tokenize(value: str) -> set[str]:
    return {item for item in value.lower().replace("\n", " ").split() if item}


class SceneHashIndexPolicy(MemoryIndexPolicy):
    kind = "scene_hash"

    def build_index(self, **kwargs: Any) -> dict[str, Any]:
        config = kwargs.get("config") or {}
        fields = list(config.get("scene_index_fields") or ["goal", "knowledge_scope", "agent_role", "thread_id"])
        payload = {
            "thread_id": kwargs.get("thread_id"),
            "task_id": kwargs.get("task_id"),
            "goal": kwargs.get("goal"),
            "agent_role": kwargs.get("agent_role"),
            "knowledge_scope": list(kwargs.get("knowledge_scope") or []),
        }
        canonical = {key: payload.get(key) for key in fields}
        digest = hashlib.sha1(json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        return {"scene_hash": digest, "fields": canonical}


class RelevanceOnlyDecayPolicy(MemoryDecayPolicy):
    kind = "relevance_only"

    def score(self, record: dict[str, Any], **kwargs: Any) -> tuple[float, dict[str, float]]:
        config = kwargs.get("config") or {}
        query_tokens = _tokenize(kwargs.get("query") or "")
        content = str(record.get("content") or "")
        content_tokens = _tokenize(content)
        metadata = dict(record.get("metadata") or {})
        overlap = len(query_tokens.intersection(content_tokens))
        relevance = overlap / max(1, len(query_tokens)) if query_tokens else 0.0
        salience = float(metadata.get("salience_score", 0.0))
        confidence = float(metadata.get("confidence", 0.0))
        reuse = float(metadata.get("reuse_count", 0.0))
        evidence_strength = float(metadata.get("evidence_count", 0.0))
        outcome_strength = float(metadata.get("outcome_strength", 0.0))
        score = (
            relevance * float(config.get("relevance_weight", 4.0))
            + salience * 0.6
            + confidence * float(config.get("evidence_weight", 1.8))
            + reuse * float(config.get("reuse_weight", 0.8))
            + evidence_strength * float(config.get("evidence_weight", 1.8))
            + outcome_strength * float(config.get("outcome_weight", 1.2))
        )
        return score, {
            "relevance": relevance,
            "salience": salience,
            "confidence": confidence,
            "reuse": reuse,
            "evidence_strength": evidence_strength,
            "outcome_strength": outcome_strength,
        }


class EpisodicSaliencePromotionPolicy(MemoryPromotionPolicy):
    kind = "episodic_salience"

    async def promote(self, manager: Any, **kwargs: Any) -> list[dict[str, Any]]:
        config = kwargs.get("config") or {}
        strategy_kind = kwargs.get("strategy_kind", "nutcracker_memory")
        final_output = kwargs.get("final_output") or ""
        retrieval_payload = kwargs.get("retrieval_payload") or {}
        task_packet = kwargs.get("task_packet") or {}
        evidence = list(retrieval_payload.get("evidence") or [])
        goal = task_packet.get("goal") or kwargs.get("user_input") or ""
        knowledge_scope = list(kwargs.get("knowledge_scope") or task_packet.get("knowledge_scope") or [])
        agent_role = kwargs.get("agent_role")
        thread_id = kwargs["thread_id"]
        task_id = task_packet.get("task_id")
        scene_index = kwargs["index_policy"].build_index(
            thread_id=thread_id,
            task_id=task_id,
            goal=goal,
            agent_role=agent_role,
            knowledge_scope=knowledge_scope,
            config=config,
        )
        query_tokens = _tokenize(goal or final_output)
        output_tokens = _tokenize(final_output)
        relevance = len(query_tokens.intersection(output_tokens)) / max(1, len(query_tokens)) if query_tokens else 0.0
        evidence_strength = min(len(evidence) / max(1, int(config.get("recall_top_k", 4))), 1.0)
        outcome_strength = min(len(final_output) / 400.0, 1.0)
        salience_score = (
            relevance * float(config.get("relevance_weight", 4.0))
            + evidence_strength * float(config.get("evidence_weight", 1.8))
            + outcome_strength * float(config.get("outcome_weight", 1.2))
        )
        results: list[dict[str, Any]] = []
        threshold = float(config.get("capsule_promotion_threshold", 1.5))
        if config.get("episodic_memory_enabled", True) and salience_score >= threshold and strategy_kind != "semantic_only":
            capsule = EpisodicCapsule(
                thread_id=thread_id,
                task_id=task_id,
                agent_role=agent_role,
                goal=goal,
                summary=(final_output[:400] if final_output else goal),
                outcome=final_output[:600],
                knowledge_scope=knowledge_scope,
                scene_index=scene_index,
                evidence_refs=[
                    {"document_id": item.get("citation", {}).get("document_id"), "source_type": item.get("source_type")}
                    for item in evidence[: int(config.get("episodic_capsule_limit", 4))]
                ],
                salience_score=salience_score,
                metadata={"strategy_kind": strategy_kind},
            )
            record_id = await manager.remember(
                MemoryRecord(
                    thread_id=thread_id,
                    kind="episodic_capsule",
                    content=capsule.summary or capsule.goal,
                    tags=["episodic", "long_term_memory"],
                    metadata={
                        "scene_index": scene_index,
                        "memory_mechanism": strategy_kind,
                        "promotion_policy": self.kind,
                        "salience_score": salience_score,
                        "evidence_refs": capsule.evidence_refs,
                        "goal": goal,
                        "task_id": task_id,
                        "agent_role": agent_role,
                        "knowledge_scope": knowledge_scope,
                        "evidence_count": len(evidence),
                        "outcome_strength": outcome_strength,
                    },
                    confidence=min(1.0, 0.5 + evidence_strength * 0.3 + outcome_strength * 0.2),
                    status="validated",
                    scope=",".join(knowledge_scope) if knowledge_scope else None,
                )
            )
            results.append({"kind": "episodic_capsule", "record_id": record_id, "salience_score": salience_score})
        semantic_threshold = float(config.get("semantic_promotion_threshold", threshold + 0.8))
        if salience_score >= semantic_threshold and strategy_kind in {"nutcracker_memory", "semantic_only", "hybrid_long_memory", "custom"}:
            record_id = await manager.remember(
                MemoryRecord(
                    thread_id=thread_id,
                    kind="semantic_memory",
                    content=(goal + ": " + final_output[:300]).strip(": "),
                    tags=["semantic", "long_term_memory"],
                    metadata={
                        "scene_index": scene_index,
                        "memory_mechanism": strategy_kind,
                        "promotion_policy": self.kind,
                        "salience_score": salience_score,
                        "goal": goal,
                        "task_id": task_id,
                        "agent_role": agent_role,
                        "knowledge_scope": knowledge_scope,
                        "evidence_count": len(evidence),
                        "outcome_strength": outcome_strength,
                    },
                    confidence=min(1.0, 0.45 + evidence_strength * 0.35 + outcome_strength * 0.2),
                    status="validated",
                    scope=",".join(knowledge_scope) if knowledge_scope else None,
                )
            )
            results.append({"kind": "semantic_memory", "record_id": record_id, "salience_score": salience_score})
        return results


class SceneFirstRecallPolicy(MemoryRecallPolicy):
    kind = "scene_first"

    async def recall(self, manager: Any, **kwargs: Any) -> list[dict[str, Any]]:
        config = kwargs.get("config") or {}
        thread_id = kwargs["thread_id"]
        query = kwargs.get("query") or ""
        knowledge_scope = list(kwargs.get("knowledge_scope") or [])
        allow_cross_thread = bool(config.get("allow_cross_thread_recall", False))
        top_k = int(config.get("recall_top_k", 4))
        strategy_kind = kwargs.get("strategy_kind", "nutcracker_memory")
        kinds = ["thread_message", "episodic_capsule", "semantic_memory"]
        if strategy_kind == "episodic_only":
            kinds = ["thread_message", "episodic_capsule"]
        elif strategy_kind == "semantic_only":
            kinds = ["semantic_memory"]
        elif strategy_kind == "mgcm":
            kinds = ["thread_message"]
        records = await manager.record_store.search(
            thread_id=None if allow_cross_thread else thread_id,
            query=query if query else None,
            kinds=kinds,
            order_desc=True,
            limit=max(top_k * 8, 12),
        )
        if strategy_kind in {"mgcm", "nutcracker_memory", "semantic_only", "hybrid_long_memory", "custom"}:
            collective_records = await manager.search_collective_memory(
                query=query,
                thread_id=None if allow_cross_thread else thread_id,
                status=None,
                limit=max(top_k * 2, 4),
            )
            for record in collective_records:
                records.append(
                    {
                        "id": record["id"],
                        "thread_id": record["thread_id"],
                        "kind": record["kind"],
                        "content": record["content"],
                        "tags": record.get("tags", []),
                        "metadata": {
                            **dict(record.get("metadata") or {}),
                            "memory_role": record.get("memory_role"),
                            "confidence": record.get("confidence"),
                            "reuse_count": record.get("reuse_count"),
                            "scope": record.get("scope"),
                        },
                    }
                )
        current_scene = kwargs["index_policy"].build_index(
            thread_id=thread_id,
            task_id=(kwargs.get("task_packet") or {}).get("task_id"),
            goal=(kwargs.get("task_packet") or {}).get("goal") or query,
            agent_role=kwargs.get("agent_role"),
            knowledge_scope=knowledge_scope,
            config=config,
        )
        ranked: list[tuple[float, dict[str, Any]]] = []
        for record in records:
            metadata = dict(record.get("metadata") or {})
            if knowledge_scope:
                record_scope = metadata.get("knowledge_scope") or metadata.get("scope")
                if isinstance(record_scope, str):
                    record_scope = [item for item in record_scope.split(",") if item]
                if record_scope and not set(record_scope).intersection(set(knowledge_scope)):
                    continue
            score, breakdown = kwargs["decay_policy"].score(
                record,
                query=query,
                knowledge_scope=knowledge_scope,
                config=config,
            )
            scene_match = 1.0 if metadata.get("scene_index", {}).get("scene_hash") == current_scene.get("scene_hash") else 0.0
            score += scene_match * 1.5
            candidate = {
                "record": record,
                "source_type": (
                    "collective_memory"
                    if metadata.get("memory_role") == "matriarch"
                    else
                    "thread_history"
                    if record["kind"] == "thread_message"
                    else record["kind"]
                ),
                "score": score,
                "score_breakdown": {**breakdown, "scene_match": scene_match},
                "scene_index": metadata.get("scene_index", {}),
            }
            ranked.append((score, candidate))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in ranked[:top_k]]
