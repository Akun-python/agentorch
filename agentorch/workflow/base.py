from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Context(BaseModel):
    thread_id: str
    user_input: str
    state: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    resume_from: str | None = None


class Node(BaseModel):
    id: str
    kind: Literal[
        "model",
        "tool",
        "router",
        "memory",
        "agent",
        "retrieve",
        "aggregate",
        "approval",
        "artifact",
        "rag_router",
        "rag_mount",
        "rag_evaluate",
        "human_notify",
        "human_input",
        "human_approval",
    ]
    config: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def model_node(cls, node_id: str, *, prompt: str | None = None, **config: Any) -> "Node":
        payload = dict(config)
        if prompt is not None:
            payload["prompt"] = prompt
        return cls(id=node_id, kind="model", config=payload)

    @classmethod
    def tool(cls, node_id: str, tool_name: str, *, arguments: dict[str, Any] | None = None, **config: Any) -> "Node":
        return cls(id=node_id, kind="tool", config={"tool_name": tool_name, "arguments": dict(arguments or {}), **config})

    @classmethod
    def agent(
        cls,
        node_id: str,
        agent_name: str,
        *,
        input_from_variable: str | None = None,
        goal: str | None = None,
        **config: Any,
    ) -> "Node":
        payload = {"agent_name": agent_name, **config}
        if input_from_variable is not None:
            payload["input_from_variable"] = input_from_variable
        if goal is not None:
            payload["goal"] = goal
        return cls(id=node_id, kind="agent", config=payload)

    @classmethod
    def retrieve(cls, node_id: str, *, question: str | None = None, output_key: str | None = None, **config: Any) -> "Node":
        payload = dict(config)
        if question is not None:
            payload["question"] = question
        if output_key is not None:
            payload["output_key"] = output_key
        return cls(id=node_id, kind="retrieve", config=payload)

    @classmethod
    def rag_mount(
        cls,
        node_id: str,
        *,
        from_variable: str,
        target_key: str = "mounted_retrieval",
        mount_result_to: str = "context",
        **config: Any,
    ) -> "Node":
        return cls(
            id=node_id,
            kind="rag_mount",
            config={
                "from_variable": from_variable,
                "target_key": target_key,
                "mount_result_to": mount_result_to,
                **config,
            },
        )

    @classmethod
    def rag_router(cls, node_id: str, *, output_key: str | None = None, **config: Any) -> "Node":
        payload = dict(config)
        if output_key is not None:
            payload["output_key"] = output_key
        return cls(id=node_id, kind="rag_router", config=payload)

    @classmethod
    def rag_evaluate(cls, node_id: str, *, from_variable: str, output_key: str | None = None, **config: Any) -> "Node":
        payload = {"from_variable": from_variable, **config}
        if output_key is not None:
            payload["output_key"] = output_key
        return cls(id=node_id, kind="rag_evaluate", config=payload)

    @classmethod
    def aggregate(cls, node_id: str, *, sources: list[str], output_key: str | None = None, **config: Any) -> "Node":
        payload = {"sources": list(sources), **config}
        if output_key is not None:
            payload["output_key"] = output_key
        return cls(id=node_id, kind="aggregate", config=payload)


class Edge(BaseModel):
    source: str
    target: str
    kind: Literal["success", "failure", "condition", "join"] = "success"
    condition: str | None = None


class Workflow(BaseModel):
    entry_node: str
    nodes: list[Node]
    edges: list[Edge]
    max_steps: int = 20

    @classmethod
    def chain(cls, *nodes: Node, entry_node: str | None = None, max_steps: int = 20) -> "Workflow":
        node_list = list(nodes)
        if not node_list:
            raise ValueError("Workflow.chain requires at least one node.")
        edges = [
            Edge(source=node_list[index].id, target=node_list[index + 1].id, kind="success")
            for index in range(len(node_list) - 1)
        ]
        return cls(entry_node=entry_node or node_list[0].id, nodes=node_list, edges=edges, max_steps=max_steps)

    def get_node(self, node_id: str) -> Node:
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise KeyError(f"Unknown node: {node_id}")

    def get_edges(self, node_id: str) -> list[Edge]:
        return [edge for edge in self.edges if edge.source == node_id]


class WorkflowBuilder:
    def __init__(self, *, max_steps: int = 20) -> None:
        self._nodes: list[Node] = []
        self._edges: list[Edge] = []
        self._entry_node: str | None = None
        self._max_steps = max_steps

    def add(self, node: Node, *, entry: bool = False) -> "WorkflowBuilder":
        self._nodes.append(node)
        if entry or self._entry_node is None:
            self._entry_node = node.id
        return self

    def connect(self, source: str, target: str, *, kind: Literal["success", "failure", "condition", "join"] = "success", condition: str | None = None) -> "WorkflowBuilder":
        self._edges.append(Edge(source=source, target=target, kind=kind, condition=condition))
        return self

    def then(self, node: Node, *, edge_kind: Literal["success", "failure", "condition", "join"] = "success", condition: str | None = None) -> "WorkflowBuilder":
        previous = self._nodes[-1] if self._nodes else None
        self.add(node, entry=previous is None)
        if previous is not None:
            self.connect(previous.id, node.id, kind=edge_kind, condition=condition)
        return self

    def build(self) -> Workflow:
        if not self._nodes or self._entry_node is None:
            raise ValueError("WorkflowBuilder cannot build an empty workflow.")
        return Workflow(entry_node=self._entry_node, nodes=list(self._nodes), edges=list(self._edges), max_steps=self._max_steps)
