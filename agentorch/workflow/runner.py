from __future__ import annotations

from typing import Any

from .base import Context, Workflow


class WorkflowRunner:
    def __init__(self, handlers: dict[str, Any] | None = None) -> None:
        self.handlers = handlers or {}

    async def run(self, workflow: Workflow, context: Context) -> dict[str, Any]:
        current = context.resume_from or workflow.entry_node
        steps = 0
        last_result: dict[str, Any] = {}
        completed_nodes: set[str] = set()
        while current and steps < workflow.max_steps:
            node = workflow.get_node(current)
            handler = self.handlers.get(node.kind)
            if handler is None:
                raise ValueError(f"No handler registered for node kind '{node.kind}'.")
            last_result = await handler(node, context)
            context.variables[node.id] = last_result
            completed_nodes.add(node.id)
            if last_result.get("status") == "waiting_human":
                return last_result
            current = self._next_node(workflow, node.id, last_result)
            if current is None:
                current = self._find_join_target(workflow, completed_nodes)
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

    def _find_join_target(self, workflow: Workflow, completed_nodes: set[str]) -> str | None:
        for node in workflow.nodes:
            incoming = [edge for edge in workflow.edges if edge.target == node.id and edge.kind == "join"]
            if incoming and all(edge.source in completed_nodes for edge in incoming) and node.id not in completed_nodes:
                return node.id
        return None
