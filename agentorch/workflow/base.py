from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Context(BaseModel):
    thread_id: str
    user_input: str
    state: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)


class Node(BaseModel):
    id: str
    kind: Literal["model", "tool", "router", "memory", "agent"]
    config: dict[str, Any] = Field(default_factory=dict)


class Edge(BaseModel):
    source: str
    target: str
    kind: Literal["success", "failure", "condition"] = "success"
    condition: str | None = None


class Workflow(BaseModel):
    entry_node: str
    nodes: list[Node]
    edges: list[Edge]
    max_steps: int = 20

    def get_node(self, node_id: str) -> Node:
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise KeyError(f"Unknown node: {node_id}")

    def get_edges(self, node_id: str) -> list[Edge]:
        return [edge for edge in self.edges if edge.source == node_id]
