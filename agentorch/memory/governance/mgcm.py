from __future__ import annotations

from typing import Any

from agentorch.memory.base import MemoryGovernance


class MGCMMemoryGovernance(MemoryGovernance):
    async def search_collective_memory(
        self,
        manager: Any,
        *,
        query: str | None = None,
        thread_id: str | None = None,
        memory_role: str = "matriarch",
        status: str | None = "validated",
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        filters: dict[str, Any] = {"memory_role": memory_role}
        if status is not None:
            filters["status"] = status
        results = await manager.record_store.search(thread_id=thread_id, metadata_filters=filters)
        ranked = []
        query_tokens = {token for token in (query or "").lower().split() if token}
        for item in results:
            normalized = manager._normalize_collective_result(item)
            haystack = f"{normalized['kind']} {normalized['content']} {' '.join(normalized['tags'])}".lower()
            overlap = sum(1 for token in query_tokens if token in haystack)
            score = float(normalized["confidence"]) + float(normalized["reuse_count"]) + overlap
            if query_tokens and overlap == 0:
                score -= 0.25
            ranked.append((score, int(normalized["id"]), normalized))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item for _, _, item in ranked[:limit]]

    async def promote_collective_memory(self, manager: Any, **kwargs: Any) -> int:
        record_type = manager.collective_record_type
        return await manager.remember(
            record_type(
                thread_id=kwargs["thread_id"],
                kind=kwargs["kind"],
                content=kwargs["content"],
                tags=kwargs.get("tags") or [],
                source_agents=kwargs.get("source_agents") or [],
                confidence=kwargs.get("confidence", 0.7),
                status=kwargs.get("status", "validated"),
                scope=kwargs.get("scope"),
                last_validated_at=manager._utc_now(),
            )
        )

    async def validate_collective_memory(self, manager: Any, record_id: int) -> dict[str, Any] | None:
        matches = await manager.record_store.search(metadata_filters={"memory_role": "matriarch"})
        target = next((item for item in matches if item["id"] == record_id), None)
        if target is None:
            return None
        metadata = dict(target.get("metadata") or {})
        metadata["status"] = "validated"
        metadata["reuse_count"] = int(metadata.get("reuse_count", 0)) + 1
        metadata["last_validated_at"] = manager._utc_now()
        await manager.record_store.update_record_metadata(record_id, metadata)
        target["metadata"] = metadata
        return manager._normalize_collective_result(target)

    async def deprecate_collective_memory(self, manager: Any, record_id: int) -> dict[str, Any] | None:
        matches = await manager.record_store.search(metadata_filters={"memory_role": "matriarch"})
        target = next((item for item in matches if item["id"] == record_id), None)
        if target is None:
            return None
        metadata = dict(target.get("metadata") or {})
        metadata["status"] = "deprecated"
        await manager.record_store.update_record_metadata(record_id, metadata)
        target["metadata"] = metadata
        return manager._normalize_collective_result(target)

    async def collect_candidate_notes(self, manager: Any, thread_id: str, *, task_id: str | None = None):
        notes = manager.session_state.workspace_notes.get(thread_id, [])
        candidates = []
        for note in notes:
            note_parent_task_id = note.metadata.get("parent_task_id")
            if task_id and note.task_id != task_id and note_parent_task_id != task_id:
                continue
            candidate_flag = note.metadata.get("collective_candidate", True)
            if candidate_flag:
                candidates.append(note)
        return list(candidates)
