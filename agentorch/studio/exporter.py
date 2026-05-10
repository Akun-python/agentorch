from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .compiler import StudioCompiledArtifact, compile_studio_dsl
from .dsl import StudioDslDocument


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
    dsl_json = _json_dump(compiled.dsl.model_dump(mode="json"))
    snippet = "\n".join(
        [
            "import json",
            "from agentorch.studio import StudioDslDocument, build_studio_agent",
            "",
            f"dsl = StudioDslDocument.model_validate(json.loads('''{dsl_json}'''))",
            "agent = build_studio_agent(dsl)",
            'result = agent.run_sync("hello from studio", thread_id="studio-sdk-snippet")',
            "print(result.output_text)",
            "agent.close()",
            "",
        ]
    )
    files = {
        "manifest.json": _json_dump(manifest),
        "studio_sdk.py": snippet,
    }
    return StudioExportArtifact(target="sdk_snippet", manifest=manifest, files=files)


def _export_python_project(compiled: StudioCompiledArtifact) -> StudioExportArtifact:
    manifest = _manifest_payload(compiled, target="python_project")
    package_name = str(compiled.dsl.meta.get("slug") or compiled.dsl.meta.get("name") or "studio_app").strip().lower().replace(" ", "_")
    main_py = "\n".join(
        [
            "from __future__ import annotations",
            "",
            "from pathlib import Path",
            "",
            "from agentorch.studio import StudioDslDocument, build_studio_agent",
            "",
            "",
            "def load_agent():",
            '    dsl_path = Path(__file__).with_name("studio_dsl.json")',
            '    dsl = StudioDslDocument.model_validate_json(dsl_path.read_text(encoding="utf-8"))',
            "    return build_studio_agent(dsl)",
            "",
            "",
            "def main() -> None:",
            "    agent = load_agent()",
            "    try:",
            '        result = agent.run_sync("hello from exported studio project", thread_id="studio-exported-main")',
            "        print(result.output_text)",
            "    finally:",
            "        agent.close()",
            "",
            "",
            'if __name__ == "__main__":',
            "    main()",
            "",
        ]
    )
    smoke_test = "\n".join(
        [
            "from __future__ import annotations",
            "",
            "from pathlib import Path",
            "",
            "from agentorch.studio import StudioDslDocument, compile_studio_dsl",
            "",
            "",
            "def test_exported_studio_project_compiles() -> None:",
            '    dsl_path = Path(__file__).parents[1] / "app" / "studio_dsl.json"',
            '    dsl = StudioDslDocument.model_validate_json(dsl_path.read_text(encoding="utf-8"))',
            "    compiled = compile_studio_dsl(dsl)",
            '    assert compiled.ir.app_type in {"agent", "team", "workflow"}',
            "",
        ]
    )
    readme = "\n".join(
        [
            f"# {compiled.dsl.meta.get('name', 'AgentTorch Studio Export')}",
            "",
            "该工程由 `agentorch.studio` 导出，保留了 DSL、IR 与最小运行入口。",
            "",
            "## 入口",
            "",
            "- `app/main.py`",
            "- `app/studio_dsl.json`",
            "- `app/studio_ir.json`",
            "",
            "## 说明",
            "",
            "- 运行前请准备模型相关环境变量",
            "- 这是单向导出工程，代码改动不会自动回写画布",
            "",
        ]
    )
    pyproject = "\n".join(
        [
            "[project]",
            f'name = "{package_name}"',
            'version = "0.1.0"',
            'requires-python = ">=3.10"',
            f'description = "Exported AgentTorch Studio project for {compiled.dsl.meta.get("name", "studio app")}"',
            'dependencies = ["masarch>=0.1.1"]',
            "",
        ]
    )
    files = {
        "manifest.json": _json_dump(manifest),
        "README.md": readme,
        "pyproject.toml": pyproject,
        ".env.example": "# 按需填写模型环境变量\nOPENAI_API_KEY=\nOPENAI_BASE_URL=\nOPENAI_MODEL=\n",
        "app/__init__.py": "",
        "app/main.py": main_py,
        "app/studio_dsl.json": _json_dump(compiled.dsl.model_dump(mode="json")),
        "app/studio_ir.json": _json_dump(compiled.ir.model_dump(mode="json")),
    }
    if compiled.dsl.export.include_tests:
        files["tests/test_smoke.py"] = smoke_test
    return StudioExportArtifact(target="python_project", manifest=manifest, files=files)
