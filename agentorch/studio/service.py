from __future__ import annotations

from pathlib import Path
from typing import Any

from .compiler import StudioBindingResolver, StudioCompiledArtifact, compile_studio_dsl, validate_studio_dsl
from .dsl import StudioDslDocument
from .exporter import StudioExportArtifact, export_studio_artifact


def load_studio_dsl(path: str | Path) -> StudioDslDocument:
    return StudioDslDocument.model_validate_json(Path(path).read_text(encoding="utf-8"))


def build_studio_agent(
    document: StudioDslDocument | dict[str, Any],
    *,
    resolver: StudioBindingResolver | None = None,
):
    compiled = compile_studio_dsl(document, resolver=resolver)
    return compiled.build()


class StudioService:
    def validate(self, document: StudioDslDocument | dict[str, Any]):
        return validate_studio_dsl(document)

    def compile(
        self,
        document: StudioDslDocument | dict[str, Any],
        *,
        resolver: StudioBindingResolver | None = None,
    ) -> StudioCompiledArtifact:
        return compile_studio_dsl(document, resolver=resolver)

    def export(
        self,
        document: StudioDslDocument | dict[str, Any] | StudioCompiledArtifact,
        *,
        target: str | None = None,
    ) -> StudioExportArtifact:
        return export_studio_artifact(document, target=target)

    def debug_run(
        self,
        document: StudioDslDocument | dict[str, Any],
        *,
        user_input: str,
        thread_id: str,
        resolver: StudioBindingResolver | None = None,
    ):
        agent = build_studio_agent(document, resolver=resolver)
        try:
            return agent.run_sync(user_input, thread_id=thread_id)
        finally:
            agent.close()
