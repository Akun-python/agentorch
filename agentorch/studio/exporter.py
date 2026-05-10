from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .compiler import StudioCompiledArtifact, compile_studio_dsl
from .dsl import StudioDslDocument
from .python_project_renderer import render_python_project_files, render_sdk_snippet


class StudioExportArtifact(BaseModel):
    target: str
    manifest: dict[str, Any]
    files: dict[str, str] = Field(default_factory=dict)

    def write_to(self, directory: str | Path) -> Path:
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        for relative_path, content in self.files.items():
            output_path = root / relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
        return root


def export_studio_artifact(
    document: StudioDslDocument | dict[str, Any] | StudioCompiledArtifact,
    *,
    target: str | None = None,
) -> StudioExportArtifact:
    compiled = document if isinstance(document, StudioCompiledArtifact) else compile_studio_dsl(document)
    selected_target = target or compiled.dsl.export.target
    if selected_target == "blueprint":
        return _export_blueprint_bundle(compiled)
    if selected_target == "sdk_snippet":
        return _export_sdk_snippet(compiled)
    return _export_python_project(compiled)


def _manifest_payload(compiled: StudioCompiledArtifact, *, target: str) -> dict[str, Any]:
    return {
        "schema_version": compiled.dsl.schema_version,
        "app_type": compiled.dsl.app_type,
        "execution_target": compiled.ir.execution_target,
        "target": target,
        "compiler": "agentorch.studio",
        "compiler_version": "v1",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "name": compiled.dsl.meta.get("name", "studio-app"),
    }


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _export_blueprint_bundle(compiled: StudioCompiledArtifact) -> StudioExportArtifact:
    manifest = _manifest_payload(compiled, target="blueprint")
    files = {
        "manifest.json": _json_dump(manifest),
        "dsl.json": _json_dump(compiled.dsl.model_dump(mode="json")),
        "ir.json": _json_dump(compiled.ir.model_dump(mode="json")),
        "blueprint.json": _json_dump(compiled.export_blueprint()),
    }
    return StudioExportArtifact(target="blueprint", manifest=manifest, files=files)


def _export_sdk_snippet(compiled: StudioCompiledArtifact) -> StudioExportArtifact:
    manifest = _manifest_payload(compiled, target="sdk_snippet")
    snippet = render_sdk_snippet(compiled)
    files = {
        "manifest.json": _json_dump(manifest),
        "studio_sdk.py": snippet,
    }
    return StudioExportArtifact(target="sdk_snippet", manifest=manifest, files=files)


def _export_python_project(compiled: StudioCompiledArtifact) -> StudioExportArtifact:
    manifest = _manifest_payload(compiled, target="python_project")
    files = render_python_project_files(compiled, manifest=manifest, json_dump=_json_dump)
    return StudioExportArtifact(target="python_project", manifest=manifest, files=files)
