from __future__ import annotations

from typing import Any

from .base import Context, Workflow


class WorkflowRunner:
    def __init__(self, handlers: dict[str, Any] | None = None) -> None:
        self.handlers = handlers or {}

    async def run(self, workflow: Workflow, context: Context) -> dict[str, Any]:
        current = workflow.entry_node
        steps = 0
        last_result: dict[str, Any] = {}
        while current and steps < workflow.max_steps:
            node = workflow.get_node(current)
            handler = self.handlers.get(node.kind)
            if handler is None:
                raise ValueError(f"No handler registered for node kind '{node.kind}'.")
            last_result = await handler(node, context)
            context.variables[node.id] = last_result
            current = self._next_node(workflow, node.id, last_result)
            steps += 1
        if steps >= workflow.max_steps:
            raise RuntimeError("Workflow exceeded maximum allowed steps.")
        return last_result

    def _next_node(self, workflow: Workflow, node_id: str, result: dict[str, Any]) -> str | None:
        edges = workflow.get_edges(node_id)
        for edge in edges:
            if edge.kind == "success":
                return edge.target
            if edge.kind == "failure" and result.get("status") == "failed":
                return edge.target
            if edge.kind == "condition" and edge.condition == result.get("route"):
                return edge.target
        return None
