from __future__ import annotations

import re

from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.models.base import BaseModelAdapter

from .models import ElephantBenchmarkCase


class ChapterProbeModel(BaseModelAdapter):
    """Deterministic local model that succeeds only when the real prompt keeps the right markers."""

    def __init__(self, case: ElephantBenchmarkCase) -> None:
        self.case = case

    def _full_text(self, request: ModelRequest) -> str:
        return "\n".join(message.content or "" for message in request.messages)

    def _agent_role(self, request: ModelRequest) -> str:
        system_message = next((message.content for message in request.messages if message.role == "system"), "")
        matched = re.search(r"Agent Role:\n([A-Za-z0-9_:-]+)", system_message)
        return matched.group(1).strip() if matched else "single_agent"

    async def generate(self, request: ModelRequest) -> ModelResponse:
        stage = str(request.metadata.get("stage") or "respond")
        if stage == "plan":
            content = "1. Gather the governing signals that survive compaction and emit the structured answer fields."
            return ModelResponse(
                message=Message(role="assistant", content=content),
                content=content,
                finish_reason="stop",
                usage=UsageInfo(total_tokens=1),
            )

        full_text = self._full_text(request)
        agent_role = self._agent_role(request)
        critical_hits = [marker for marker in self.case.critical_markers if marker in full_text]
        distractor_hits = [marker for marker in self.case.distractor_markers if marker in full_text]
        success = len(critical_hits) == len(self.case.critical_markers) and bool(self.case.critical_markers)
        fallback_by_role = {
            "planner": "PLANNER_MISSING_CONTEXT",
            "evidence_scout": "SCOUT_PENDING",
            "reviewer": "REVIEW_NEEDS_CONTEXT",
            "single_agent": "SINGLE_AGENT_MISSING_CONTEXT",
        }
        fallback = fallback_by_role.get(agent_role, "PROBE_MISSING_CONTEXT")
        lines = [
            f"agent_role: {agent_role}",
            f"stage: {stage}",
            f"case_id: {self.case.case_id}",
            f"critical_markers_found: {','.join(critical_hits) if critical_hits else 'none'}",
            f"distractor_markers_found: {','.join(distractor_hits) if distractor_hits else 'none'}",
        ]
        if success and agent_role in {"planner", "single_agent"}:
            for key, value in self.case.expected_answer_fields.items():
                lines.append(f"{key}: {value}")
        else:
            for key in self.case.expected_answer_fields:
                lines.append(f"{key}: {fallback}")
        content = "\n".join(lines)
        return ModelResponse(
            message=Message(role="assistant", content=content),
            content=content,
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


__all__ = ["ChapterProbeModel"]
