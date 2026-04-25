from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from agentorch.workflow import Node, Workflow, WorkflowBuilder

WorkflowTemplateFactory = Callable[..., Workflow | None]


def _clone_workflow(workflow: Workflow | None) -> Workflow | None:
    return workflow.model_copy(deep=True) if workflow is not None else None


def _classic_inline_answer(**kwargs: Any) -> Workflow:
    return Workflow.chain(
        Node.model_node("answer", prompt=kwargs.get("prompt")),
        max_steps=int(kwargs.get("max_steps", 8)),
    )


def _retrieve_plan_review(**kwargs: Any) -> Workflow:
    retrieve_key = kwargs.get("retrieve_output_key", "retrieved")
    return (
        WorkflowBuilder(max_steps=int(kwargs.get("max_steps", 12)))
        .then(
            Node.retrieve(
                "retrieve",
                question=kwargs.get("question"),
                output_key=retrieve_key,
                rag_mode=kwargs.get("rag_mode", "hybrid"),
                must_cover=list(kwargs.get("must_cover", [])),
                file_types=list(kwargs.get("file_types", [])),
            )
        )
        .then(
            Node.model_node(
                "review",
                prompt=kwargs.get(
                    "review_prompt",
                    "Use the workflow task packet and retrieved evidence to plan, review, and answer the user's request.",
                ),
                task_context_from_variables=[retrieve_key],
            )
        )
        .build()
    )


def _retrieve_delegate_aggregate(**kwargs: Any) -> Workflow:
    retrieve_key = kwargs.get("retrieve_output_key", "retrieved")
    plan_key = kwargs.get("plan_output_key", "plan")
    review_key = kwargs.get("review_output_key", "review")
    combined_key = kwargs.get("combined_output_key", "combined")
    return (
        WorkflowBuilder(max_steps=int(kwargs.get("max_steps", 16)))
        .then(
            Node.retrieve(
                "retrieve",
                question=kwargs.get("question"),
                output_key=retrieve_key,
                rag_mode=kwargs.get("rag_mode", "hybrid"),
                must_cover=list(kwargs.get("must_cover", [])),
                file_types=list(kwargs.get("file_types", [])),
            )
        )
        .then(
            Node.model_node(
                "plan",
                prompt=kwargs.get(
                    "plan_prompt",
                    "Draft a plan using the workflow task packet and retrieved evidence.",
                ),
                output_key=plan_key,
                task_context_from_variables=[retrieve_key],
            )
        )
        .then(
            Node.model_node(
                "review",
                prompt=kwargs.get(
                    "review_prompt",
                    "Review the draft plan using the retrieved evidence and produce an improved answer.",
                ),
                output_key=review_key,
                task_context_from_variables=[retrieve_key, plan_key],
            )
        )
        .then(Node.aggregate("aggregate", sources=[retrieve_key, plan_key, review_key], output_key=combined_key))
        .then(
            Node.model_node(
                "finalize",
                prompt=kwargs.get(
                    "final_prompt",
                    "Synthesize the aggregated workflow outputs into the final answer.",
                ),
                task_context_from_variables=[retrieve_key, plan_key, review_key, combined_key],
            )
        )
        .build()
    )


_BUILTIN_TEMPLATES: dict[str, WorkflowTemplateFactory] = {
    "classic_inline_answer": _classic_inline_answer,
    "retrieve_plan_review": _retrieve_plan_review,
    "retrieve_delegate_aggregate": _retrieve_delegate_aggregate,
}


def register_evolution_workflow_template(name: str, factory: WorkflowTemplateFactory) -> None:
    _BUILTIN_TEMPLATES[str(name)] = factory


def get_evolution_workflow_template(name: str) -> WorkflowTemplateFactory:
    try:
        return _BUILTIN_TEMPLATES[str(name)]
    except KeyError as exc:
        raise ValueError(f"Unsupported evolution workflow template: {name}") from exc


def list_evolution_workflow_templates() -> list[str]:
    return sorted(_BUILTIN_TEMPLATES.keys())


def resolve_evolution_workflow_template(
    template: str | Workflow | WorkflowTemplateFactory | None,
    *,
    templates: Mapping[str, Workflow | WorkflowTemplateFactory] | None = None,
    **kwargs: Any,
) -> Workflow | None:
    if template is None:
        return None
    if isinstance(template, Workflow):
        return _clone_workflow(template)
    if callable(template):
        return _clone_workflow(template(**kwargs))
    if templates and str(template) in templates:
        override = templates[str(template)]
        if isinstance(override, Workflow):
            return _clone_workflow(override)
        return _clone_workflow(override(**kwargs))
    return _clone_workflow(get_evolution_workflow_template(str(template))(**kwargs))
