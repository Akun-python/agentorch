from __future__ import annotations

from typing import Any

from agentorch.security import RedactionConfig, sanitize_for_export
from agentorch.workflow import Workflow


def _safe_export(value: Any, *, config: RedactionConfig | dict[str, object] | None = None, unsafe: bool = False) -> Any:
    return sanitize_for_export(value, config=config, unsafe=unsafe)


def _workflow_summary(workflow: Workflow | None) -> dict[str, Any] | None:
    if workflow is None:
        return None
    return {
        "entry_node": workflow.entry_node,
        "max_steps": workflow.max_steps,
        "nodes": [
            {"id": node.id, "kind": node.kind, "config": _safe_export(node.config)}
            for node in workflow.nodes
        ],
        "edges": [
            {
                "source": edge.source,
                "target": edge.target,
                "kind": edge.kind,
                "condition": edge.condition,
            }
            for edge in workflow.edges
        ],
    }
