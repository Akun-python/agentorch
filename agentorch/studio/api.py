from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from .compiler import compile_studio_dsl
from .dsl import StudioDslDocument
from .exporter import export_studio_artifact
from .service import StudioService


class _StudioDocumentRequest(BaseModel):
    document: StudioDslDocument


class _StudioExportRequest(BaseModel):
    document: StudioDslDocument
    target: str | None = None


def create_studio_router(service: StudioService | None = None):
    try:
        from fastapi import APIRouter
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("FastAPI is not installed. Install `fastapi` before using create_studio_router().") from exc

    studio_service = service or StudioService()
    router = APIRouter(prefix="/studio", tags=["studio"])

    @router.post("/validate")
    def validate_document(request: _StudioDocumentRequest) -> dict[str, Any]:
        issues = studio_service.validate(request.document)
        return {
            "ok": not any(issue.severity == "error" for issue in issues),
            "issues": [issue.model_dump() for issue in issues],
        }

    @router.post("/compile")
    def compile_document(request: _StudioDocumentRequest) -> dict[str, Any]:
        compiled = compile_studio_dsl(request.document)
        return {
            "ok": True,
            "ir": compiled.ir.model_dump(mode="json"),
            "blueprint": compiled.export_blueprint(),
            "issues": [issue.model_dump() for issue in compiled.issues],
        }

    @router.post("/exports")
    def export_document(request: _StudioExportRequest) -> dict[str, Any]:
        artifact = export_studio_artifact(request.document, target=request.target)
        return {
            "ok": True,
            "target": artifact.target,
            "manifest": artifact.manifest,
            "files": artifact.files,
        }

    return router
