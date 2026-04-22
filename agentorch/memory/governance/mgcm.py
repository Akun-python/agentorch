from __future__ import annotations

from typing import Any, Literal

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

    async def resolve_conflict(
        self,
        manager: Any,
        record_a_id: int,
        record_b_id: int,
        resolution: Literal["supersede", "merge", "keep_both"],
        *,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Resolve conflicts between two collective memories.

        Args:
            manager: MemoryManager instance
            record_a_id: ID of first conflicting record
            record_b_id: ID of second conflicting record
            resolution: Resolution strategy
            reason: Optional reason for the resolution

        Returns:
            Resolution result with status and affected record IDs
        """
        matches = await manager.record_store.search(metadata_filters={"memory_role": "matriarch"})
        record_a = next((item for item in matches if item["id"] == record_a_id), None)
        record_b = next((item for item in matches if item["id"] == record_b_id), None)

        if record_a is None or record_b is None:
            return {"status": "error", "message": "One or both records not found"}

        if resolution == "supersede":
            # Mark older record as deprecated and link to newer
            metadata_a = dict(record_a.get("metadata") or {})
            metadata_a["status"] = "deprecated"
            metadata_a["superseded_by"] = record_b_id
            metadata_a["deprecation_reason"] = reason or "superseded"
            await manager.record_store.update_record_metadata(record_a_id, metadata_a)

            metadata_b = dict(record_b.get("metadata") or {})
            metadata_b["supersedes"] = metadata_b.get("supersedes", [])
            if isinstance(metadata_b["supersedes"], list):
                metadata_b["supersedes"].append(record_a_id)
            else:
                metadata_b["supersedes"] = [record_a_id]
            await manager.record_store.update_record_metadata(record_b_id, metadata_b)

            return {
                "status": "resolved",
                "resolution": "supersede",
                "deprecated_id": record_a_id,
                "active_id": record_b_id,
                "reason": reason,
            }

        elif resolution == "merge":
            # Create new merged record
            content_a = record_a.get("content", "")
            content_b = record_b.get("content", "")
            merged_content = f"{content_a}; {content_b}"

            metadata_a = dict(record_a.get("metadata") or {})
            metadata_b = dict(record_b.get("metadata") or {})

            tags_a = set(record_a.get("tags", []))
            tags_b = set(record_b.get("tags", []))
            merged_tags = list(tags_a.union(tags_b))

            source_agents_a = set(metadata_a.get("source_agents", []))
            source_agents_b = set(metadata_b.get("source_agents", []))
            merged_sources = list(source_agents_a.union(source_agents_b))

            confidence = max(
                float(metadata_a.get("confidence", 0.5)),
                float(metadata_b.get("confidence", 0.5)),
            )

            merged_id = await self.promote_collective_memory(
                manager,
                thread_id=record_a.get("thread_id"),
                kind=record_a.get("kind", "merged"),
                content=merged_content,
                tags=merged_tags,
                source_agents=merged_sources,
                confidence=confidence,
                status="validated",
            )

            # Deprecate both original records
            for record_id in [record_a_id, record_b_id]:
                metadata = await manager.record_store.search(metadata_filters={"memory_role": "matriarch"})
                target = next((item for item in metadata if item["id"] == record_id), None)
                if target:
                    meta = dict(target.get("metadata") or {})
                    meta["status"] = "deprecated"
                    meta["merged_into"] = merged_id
                    meta["deprecation_reason"] = reason or "merged"
                    await manager.record_store.update_record_metadata(record_id, meta)

            return {
                "status": "resolved",
                "resolution": "merge",
                "deprecated_ids": [record_a_id, record_b_id],
                "merged_id": merged_id,
                "reason": reason,
            }

        elif resolution == "keep_both":
            # Mark both as reviewed but keep active
            for record_id in [record_a_id, record_b_id]:
                matches = await manager.record_store.search(metadata_filters={"memory_role": "matriarch"})
                target = next((item for item in matches if item["id"] == record_id), None)
                if target:
                    metadata = dict(target.get("metadata") or {})
                    metadata["conflict_reviewed"] = True
                    metadata["conflict_with"] = record_b_id if record_id == record_a_id else record_a_id
                    metadata["conflict_resolution"] = "keep_both"
                    metadata["conflict_reason"] = reason or "both valid"
                    await manager.record_store.update_record_metadata(record_id, metadata)

            return {
                "status": "resolved",
                "resolution": "keep_both",
                "record_ids": [record_a_id, record_b_id],
                "reason": reason,
            }

        return {"status": "error", "message": f"Unknown resolution strategy: {resolution}"}

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
