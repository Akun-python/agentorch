from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agentorch.knowledge import RetrievalIntent

from .base import FunctionTool


class DeliberativeRetrieveInput(BaseModel):
    question: str
    goal: str | None = None
    rag_mode: str = "deliberative"
    mount: str | None = None
    injection_policy: str | None = None
    must_cover: list[str] = Field(default_factory=list)
    knowledge_scope: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    file_types: list[str] = Field(default_factory=list)
    max_steps: int = 3
    max_documents: int = 8
    path_filters: list[str] = Field(default_factory=list)
    mime_filters: list[str] = Field(default_factory=list)


class SearchKnowledgeAssetsInput(BaseModel):
    source_types: list[str] = Field(default_factory=list)
    file_types: list[str] = Field(default_factory=list)


class OpenRetrievedEvidenceInput(BaseModel):
    document_id: str
    section_id: str | None = None


def create_deliberative_retrieve_tool(runtime: Any, *, name: str = "deliberative_retrieve") -> FunctionTool:
    async def deliberate(input: DeliberativeRetrieveInput):
        payload = await runtime._build_retrieval_context(
            input.question,
            runtime._create_context_envelope(thread_id="tool:deliberative_retrieve"),
            knowledge_scope=input.knowledge_scope or runtime.config.default_knowledge_scope,
            retrieval_overrides={
                "goal": input.goal,
                "rag_mode": input.rag_mode,
                "mount": input.mount,
                "injection_policy": input.injection_policy,
                "must_cover": input.must_cover,
                "sources": input.sources,
                "file_types": input.file_types,
                "max_steps": input.max_steps,
                "max_documents": input.max_documents,
                "path_filters": input.path_filters,
                "mime_filters": input.mime_filters,
            },
        )
        return payload

    return FunctionTool(
        name=name,
        description="Run deliberative multi-format retrieval over local knowledge, artifacts, and memory-backed sources.",
        input_model=DeliberativeRetrieveInput,
        func=deliberate,
    )


def create_search_knowledge_assets_tool(runtime: Any, *, name: str = "search_knowledge_assets") -> FunctionTool:
    async def search_assets(input: SearchKnowledgeAssetsInput):
        knowledge_base = runtime.knowledge_base
        if knowledge_base is None or not hasattr(knowledge_base, "list_assets"):
            return {"assets": []}
        assets = knowledge_base.list_assets(source_types=input.source_types, file_types=input.file_types)
        return {"assets": [asset.model_dump() for asset in assets]}

    return FunctionTool(
        name=name,
        description="List indexed knowledge assets by source type or file type.",
        input_model=SearchKnowledgeAssetsInput,
        func=search_assets,
    )


def create_open_retrieved_evidence_tool(runtime: Any, *, name: str = "open_retrieved_evidence") -> FunctionTool:
    async def open_evidence(input: OpenRetrievedEvidenceInput):
        knowledge_base = runtime.knowledge_base
        if knowledge_base is None or not hasattr(knowledge_base, "get_document"):
            return {"document": None}
        document = knowledge_base.get_document(input.document_id)
        if input.section_id:
            sections = [section.model_dump() for section in document.sections if section.section_id == input.section_id]
        else:
            sections = [section.model_dump() for section in document.sections]
        return {"document": document.model_dump(), "sections": sections}

    return FunctionTool(
        name=name,
        description="Open a retrieved document or one of its structured sections for closer inspection.",
        input_model=OpenRetrievedEvidenceInput,
        func=open_evidence,
    )
