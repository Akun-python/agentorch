from __future__ import annotations

import json
import pprint
from pathlib import Path
from textwrap import dedent
from typing import Any

from .compiler import StudioCompiledArtifact
from .dsl import StudioCanvasNode, StudioDslDocument

_TOOL_BUNDLE_FIELD_MAP = {
    "filesystem": "include_filesystem",
    "execution": "include_execution",
    "git": "include_git",
    "web": "include_web",
    "media": "include_media",
}


def render_python_project_files(
    compiled: StudioCompiledArtifact,
    *,
    manifest: dict[str, Any],
    json_dump: Any,
) -> dict[str, str]:
    dsl = compiled.dsl
    package_name = _package_name(dsl)
    files: dict[str, str] = {
        "manifest.json": json_dump(manifest),
        "README.md": _render_readme(compiled),
        "pyproject.toml": _render_pyproject(package_name, compiled),
        ".env.example": _render_env_example(dsl),
        "app/__init__.py": "",
        "app/main.py": _render_main_entry(),
        "app/diamond.py": _render_diamond_entry(dsl),
        "app/runtime.py": _render_runtime_helpers(),
        "app/bindings/__init__.py": "",
        "app/bindings/models.py": _render_model_bindings_module(),
        "app/bindings/tools.py": _render_tool_bindings_module(),
        "app/bindings/knowledge.py": _render_knowledge_bindings_module(),
        "app/bindings/secrets.py": _render_secret_bindings_module(),
        "configs/app.json": json_dump(_app_config_payload(compiled)),
        "configs/models.json": json_dump([binding.model_dump(mode="json") for binding in dsl.bindings.models]),
        "configs/tools.json": json_dump([binding.model_dump(mode="json") for binding in dsl.bindings.tools]),
        "configs/knowledge_sources.json": json_dump(
            [binding.model_dump(mode="json") for binding in dsl.bindings.knowledge_sources]
        ),
        "configs/secrets.json": json_dump([binding.model_dump(mode="json") for binding in dsl.bindings.secrets]),
        "configs/blueprint.json": json_dump(compiled.export_blueprint()),
        "app/studio_dsl.json": json_dump(dsl.model_dump(mode="json")),
        "app/studio_ir.json": json_dump(compiled.ir.model_dump(mode="json")),
    }

    files.update(_render_app_specific_files(compiled))

    if dsl.export.include_tests:
        files["tests/test_smoke.py"] = _render_smoke_test(compiled)
    return files


def render_sdk_snippet(compiled: StudioCompiledArtifact) -> str:
    dsl = compiled.dsl
    if dsl.app_type == "agent":
        return _render_agent_snippet(compiled)
    if dsl.app_type == "team":
        return _render_team_snippet(compiled)
    return _render_workflow_snippet(compiled)


def _package_name(dsl: StudioDslDocument) -> str:
    return str(dsl.meta.get("slug") or dsl.meta.get("name") or "studio_app").strip().lower().replace(" ", "_")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump(mode="json"))
    return value


def _py_literal(value: Any) -> str:
    return pprint.pformat(_json_safe(value), sort_dicts=False, width=100)


def _quoted(value: str | None) -> str:
    return repr(value) if value is not None else "None"


def _app_config_payload(compiled: StudioCompiledArtifact) -> dict[str, Any]:
    return {
        "name": compiled.dsl.meta.get("name", "studio-export"),
        "slug": compiled.dsl.meta.get("slug", "studio-export"),
        "app_type": compiled.dsl.app_type,
        "execution_target": compiled.ir.execution_target,
        "diamond_entry": "app.diamond:build_diamond",
        "python_entry": "app.main:main",
        "compiler": "agentorch.studio",
        "compiler_version": "v1",
    }


def _runtime_config_payload(
    dsl: StudioDslDocument,
    *,
    reasoning: Any | None = None,
    knowledge_scope: list[str] | None = None,
    include_max_steps: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if reasoning is not None:
        payload["reasoning_strategy"] = reasoning
    for key in ("context_policy", "state_policy", "coordination_policy", "memory_policy", "rag_strategy"):
        if key in dsl.runtime.policies:
            payload[key] = dsl.runtime.policies[key]
    if "rag_strategy" in payload:
        rag_strategy = payload["rag_strategy"]
        if isinstance(rag_strategy, dict):
            payload["enable_retrieval"] = rag_strategy.get("mode", "off") != "off"
    if knowledge_scope:
        payload["default_knowledge_scope"] = list(knowledge_scope)
    if "enable_streaming" in dsl.runtime.debug:
        payload["enable_streaming"] = bool(dsl.runtime.debug["enable_streaming"])
    if include_max_steps and "max_steps" in dsl.runtime.debug:
        payload["max_steps"] = int(dsl.runtime.debug["max_steps"])
    return payload


def _render_readme(compiled: StudioCompiledArtifact) -> str:
    dsl = compiled.dsl
    return "\n".join(
        [
            f"# {dsl.meta.get('name', 'AgentTorch Studio Export')}",
            "",
            "该工程由 `agentorch.studio` 导出，包含可直接阅读和修改的框架装配代码。",
            "",
            "## 主要入口",
            "",
            "- `app/main.py`：命令行入口",
            "- `app/diamond.py`：Python 环境运行入口",
            "- `configs/app.json`：导出元信息",
            "- `app/studio_dsl.json`：原始 DSL 快照",
            "- `app/studio_ir.json`：编译后的 IR 快照",
            "",
            "## 说明",
            "",
            "- `agent` / `team` 会直接导出为 `AgentDesign` / `TeamDesign` 装配代码。",
            "- `workflow` 会导出为公开 `Workflow` 结构与一层最薄的 `StudioWorkflowRuntimePlan` 运行壳。",
            "- `diamond.py` 会统一返回可运行的框架智能体对象，便于在 Python 环境集成。",
            "- Secret 只保留环境变量引用，不会导出明文。",
            "",
        ]
    )


def _render_pyproject(package_name: str, compiled: StudioCompiledArtifact) -> str:
    return "\n".join(
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


def _render_env_example(dsl: StudioDslDocument) -> str:
    lines = [
        "# 运行前按需填写环境变量",
    ]
    exported: set[str] = set()
    for secret in dsl.bindings.secrets:
        if secret.env_var not in exported:
            lines.append(f"{secret.env_var}=")
            exported.add(secret.env_var)
    if not exported and any(binding.provider == "openai" for binding in dsl.bindings.models):
        lines.extend(
            [
                "OPENAI_API_KEY=",
                "OPENAI_BASE_URL=",
                "OPENAI_MODEL=",
            ]
        )
    return "\n".join(lines) + "\n"


def _render_main_entry() -> str:
    return dedent(
        """
        from __future__ import annotations

        import argparse

        from app.diamond import run_diamond


        def main() -> None:
            parser = argparse.ArgumentParser(description="Run exported AgentTorch Studio diamond entry.")
            parser.add_argument("user_input", nargs="?", default="hello from exported diamond")
            parser.add_argument("--thread-id", default="diamond-exported-main")
            args = parser.parse_args()
            print(run_diamond(args.user_input, thread_id=args.thread_id))


        if __name__ == "__main__":
            main()
        """
    ).strip() + "\n"


def _render_runtime_helpers() -> str:
    return dedent(
        """
        from __future__ import annotations

        import json
        import os
        from pathlib import Path
        from typing import Any

        BASE_DIR = Path(__file__).resolve().parents[1]
        CONFIG_DIR = BASE_DIR / "configs"


        def load_config_json(name: str) -> Any:
            return json.loads((CONFIG_DIR / name).read_text(encoding="utf-8"))


        def compact_dict(payload: dict[str, Any]) -> dict[str, Any]:
            return {key: value for key, value in payload.items() if value not in (None, [], {}, "")}


        def read_env(name: str) -> str | None:
            value = os.getenv(name)
            return value if value else None


        def dedupe(values: list[str]) -> list[str]:
            return list(dict.fromkeys(item for item in values if item))
        """
    ).strip() + "\n"


def _render_model_bindings_module() -> str:
    return dedent(
        """
        from __future__ import annotations

        from typing import Any

        from app.runtime import compact_dict, load_config_json, read_env

        MODEL_BINDINGS = load_config_json("models.json")


        def _apply_provider_env_overrides(payload: dict[str, Any]) -> dict[str, Any]:
            provider = str(payload.get("provider") or "").lower()
            resolved = dict(payload)
            if provider == "openai":
                resolved["api_key"] = resolved.get("api_key") or read_env("OPENAI_API_KEY")
                resolved["base_url"] = resolved.get("base_url") or read_env("OPENAI_BASE_URL")
                resolved["model"] = resolved.get("model") or read_env("OPENAI_MODEL")
            return compact_dict(resolved)


        def resolve_model_binding(name: str) -> dict[str, Any] | str | None:
            binding = next((item for item in MODEL_BINDINGS if item["name"] == name), None)
            if binding is None:
                raise KeyError(f"Unknown model binding: {name}")
            payload = dict(binding.get("config") or {})
            if binding.get("provider") and "provider" not in payload:
                payload["provider"] = binding["provider"]
            if binding.get("model") and "model" not in payload:
                payload["model"] = binding["model"]
            if payload:
                return _apply_provider_env_overrides(payload)
            return binding.get("model")


        def split_model_binding(name: str) -> tuple[str | None, dict[str, Any] | None]:
            binding = resolve_model_binding(name)
            if isinstance(binding, str):
                return binding, None
            if isinstance(binding, dict):
                return binding.get("model"), binding
            return None, None
        """
    ).strip() + "\n"


def _render_tool_bindings_module() -> str:
    return dedent(
        f"""
        from __future__ import annotations

        from typing import Any

        from app.runtime import load_config_json

        TOOL_BINDINGS = load_config_json("tools.json")
        BUNDLE_FIELD_MAP = {_py_literal(_TOOL_BUNDLE_FIELD_MAP)}


        def build_tool_bundles(binding_names: list[str]) -> dict[str, Any] | None:
            payload: dict[str, Any] = {{}}
            for binding_name in binding_names:
                binding = next((item for item in TOOL_BINDINGS if item["name"] == binding_name), None)
                if binding is None:
                    raise KeyError(f"Unknown tool binding: {{binding_name}}")
                bundle = binding.get("bundle")
                if bundle and bundle in BUNDLE_FIELD_MAP:
                    payload[BUNDLE_FIELD_MAP[bundle]] = True
            return payload or None


        def unresolved_tool_names(binding_names: list[str]) -> list[str]:
            names: list[str] = []
            for binding_name in binding_names:
                binding = next((item for item in TOOL_BINDINGS if item["name"] == binding_name), None)
                if binding is None:
                    raise KeyError(f"Unknown tool binding: {{binding_name}}")
                if not binding.get("bundle") and binding.get("tool_name"):
                    names.append(binding["tool_name"])
            return names
        """
    ).strip() + "\n"


def _render_knowledge_bindings_module() -> str:
    return dedent(
        """
        from __future__ import annotations

        from app.runtime import dedupe, load_config_json

        KNOWLEDGE_BINDINGS = load_config_json("knowledge_sources.json")


        def resolve_knowledge_paths(binding_names: list[str]) -> list[str]:
            paths: list[str] = []
            for binding_name in binding_names:
                binding = next((item for item in KNOWLEDGE_BINDINGS if item["name"] == binding_name), None)
                if binding is None:
                    raise KeyError(f"Unknown knowledge binding: {binding_name}")
                path = binding.get("path")
                if path:
                    paths.append(path)
            return dedupe(paths)


        def resolve_knowledge_scope(binding_names: list[str]) -> list[str]:
            scopes: list[str] = []
            for binding_name in binding_names:
                binding = next((item for item in KNOWLEDGE_BINDINGS if item["name"] == binding_name), None)
                if binding is None:
                    raise KeyError(f"Unknown knowledge binding: {binding_name}")
                scopes.extend(binding.get("scope") or [])
            return dedupe(scopes)
        """
    ).strip() + "\n"


def _render_secret_bindings_module() -> str:
    return dedent(
        """
        from __future__ import annotations

        from app.runtime import load_config_json, read_env

        SECRET_BINDINGS = load_config_json("secrets.json")


        def resolve_secret_env_map() -> dict[str, str]:
            return {item["name"]: item["env_var"] for item in SECRET_BINDINGS}


        def read_named_secret(name: str) -> str | None:
            env_map = resolve_secret_env_map()
            env_var = env_map.get(name)
            return read_env(env_var) if env_var else None
        """
    ).strip() + "\n"


def _render_diamond_entry(dsl: StudioDslDocument) -> str:
    if dsl.app_type == "agent":
        import_line = "from app.agents.main_agent import build_agent"
        builder_name = "build_agent"
    elif dsl.app_type == "team":
        import_line = "from app.teams.main_team import build_team"
        builder_name = "build_team"
    else:
        import_line = "from app.workflows.main_workflow import build_workflow_agent"
        builder_name = "build_workflow_agent"
    return dedent(
        f"""
        from __future__ import annotations

        {import_line}


        def build_diamond():
            return {builder_name}()


        def run_diamond(user_input: str, *, thread_id: str = "diamond-exported-main") -> str:
            diamond = build_diamond()
            try:
                result = diamond.run_sync(user_input, thread_id=thread_id)
                return result.output_text
            finally:
                diamond.close()
        """
    ).strip() + "\n"


def _render_app_specific_files(compiled: StudioCompiledArtifact) -> dict[str, str]:
    dsl = compiled.dsl
    if dsl.app_type == "agent":
        return {
            "app/agents/__init__.py": "",
            "app/agents/main_agent.py": _render_agent_module(compiled),
        }
    if dsl.app_type == "team":
        return {
            "app/teams/__init__.py": "",
            "app/teams/main_team.py": _render_team_module(compiled),
        }
    return {
        "app/workflows/__init__.py": "",
        "app/workflows/roles.py": _render_workflow_roles_module(compiled),
        "app/workflows/main_workflow.py": _render_workflow_module(compiled),
    }


def _render_agent_module(compiled: StudioCompiledArtifact) -> str:
    dsl = compiled.dsl
    llm_node = next(node for node in dsl.canvas.nodes if node.kind == "llm_agent")
    model_binding = llm_node.config.get("model_binding") or _default_model_binding_name(dsl)
    tool_bindings = list(llm_node.config.get("tool_bindings", []))
    knowledge_bindings = list(llm_node.config.get("knowledge_bindings", []))
    knowledge_scope = _merged_knowledge_scope(dsl, knowledge_bindings)
    runtime_config = _runtime_config_payload(
        dsl,
        reasoning=llm_node.config.get("reasoning"),
        knowledge_scope=knowledge_scope,
        include_max_steps=True,
    )
    return dedent(
        f"""
        from __future__ import annotations

        from agentorch import AgentDesign

        from app.bindings.knowledge import resolve_knowledge_paths, resolve_knowledge_scope
        from app.bindings.models import resolve_model_binding
        from app.bindings.tools import build_tool_bundles, unresolved_tool_names

        MODEL_BINDING = {_quoted(model_binding)}
        TOOL_BINDINGS = {_py_literal(tool_bindings)}
        KNOWLEDGE_BINDINGS = {_py_literal(knowledge_bindings)}
        RUNTIME_CONFIG = {_py_literal(runtime_config)}


        def build_agent_design() -> AgentDesign:
            knowledge_paths = resolve_knowledge_paths(KNOWLEDGE_BINDINGS)
            knowledge_scope = resolve_knowledge_scope(KNOWLEDGE_BINDINGS)
            tool_bundles = build_tool_bundles(TOOL_BINDINGS)
            unresolved = unresolved_tool_names(TOOL_BINDINGS)
            if unresolved:
                print("未自动装配的自定义工具，请按需补充：", ", ".join(unresolved))
            return AgentDesign(
                name={_quoted(llm_node.name or dsl.meta.get("name"))},
                description={_quoted(llm_node.config.get("description") or dsl.meta.get("description"))},
                profile={_quoted(str(llm_node.config.get("profile", "default")))},
                model=resolve_model_binding(MODEL_BINDING) if MODEL_BINDING else None,
                system_prompt={_quoted(llm_node.config.get("system_prompt"))},
                enable_tools=True if TOOL_BINDINGS else None,
                tool_bundles=tool_bundles,
                enable_rag=True if KNOWLEDGE_BINDINGS else None,
                knowledge_paths=knowledge_paths or None,
                knowledge_scope=knowledge_scope or None,
                reasoning={_py_literal(llm_node.config.get("reasoning"))},
                context_policy={_py_literal(dsl.runtime.policies.get("context_policy"))},
                state_policy={_py_literal(dsl.runtime.policies.get("state_policy"))},
                coordination_policy={_py_literal(dsl.runtime.policies.get("coordination_policy"))},
                memory_policy={_py_literal(dsl.runtime.policies.get("memory_policy"))},
                runtime_config=RUNTIME_CONFIG or None,
            )


        def build_agent():
            return build_agent_design().build()
        """
    ).strip() + "\n"


def _render_team_module(compiled: StudioCompiledArtifact) -> str:
    dsl = compiled.dsl
    role_nodes = [node for node in dsl.canvas.nodes if node.kind == "sub_agent"]
    helpers: list[str] = []
    add_role_lines: list[str] = []
    for node in role_nodes:
        helper_name = f"build_{_safe_identifier(node.id)}_design"
        helpers.append(_render_team_role_helper(dsl, node, helper_name))
        knowledge_bindings = list(node.config.get("knowledge_bindings", []))
        add_role_lines.append(
            "\n".join(
                [
                    "    team = team.add_role(",
                    f"        {_quoted(str(node.config.get('agent_name') or node.name or node.id))},",
                    f"        role={_quoted(node.config.get('role'))},",
                    f"        description={_quoted(node.config.get('description'))},",
                    f"        design={helper_name}(),",
                    f"        capabilities={_py_literal(list(node.config.get('capabilities', []) or []))},",
                    f"        tags={_py_literal(list(node.config.get('tags', []) or []))},",
                    f"        supports_parallel_tasks={bool(node.config.get('supports_parallel_tasks', False))},",
                    f"        max_delegation_depth={int(node.config.get('max_delegation_depth', 1) or 1)},",
                    f"        knowledge_scope={_py_literal(_merged_knowledge_scope(dsl, knowledge_bindings)) or 'None'},",
                    "    )",
                ]
            )
        )
    runtime_config = _runtime_config_payload(dsl, include_max_steps=True)
    helper_block = "\n\n".join(helpers)
    body_lines = [
        "def build_team_design() -> TeamDesign:",
        "    team = TeamDesign(",
        f"        name={_quoted(dsl.meta.get('name'))},",
        f"        description={_quoted(dsl.meta.get('description'))},",
        f"        topology={_quoted(str(dsl.meta.get('topology', 'supervisor')))},",
        f"        coordination_policy={_py_literal(dsl.runtime.policies.get('coordination_policy'))},",
        f"        context_policy={_py_literal(dsl.runtime.policies.get('context_policy'))},",
        f"        state_policy={_py_literal(dsl.runtime.policies.get('state_policy'))},",
        f"        memory_policy={_py_literal(dsl.runtime.policies.get('memory_policy'))},",
        "        runtime_config=TEAM_RUNTIME_CONFIG or None,",
        "    )",
    ]
    if add_role_lines:
        body_lines.extend(add_role_lines)
    body_lines.append("    return team")
    module_lines = [
        "from __future__ import annotations",
        "",
        "from agentorch import AgentDesign, TeamDesign",
        "from app.bindings.knowledge import resolve_knowledge_paths, resolve_knowledge_scope",
        "from app.bindings.models import resolve_model_binding",
        "from app.bindings.tools import build_tool_bundles, unresolved_tool_names",
        "",
        helper_block,
        "",
        f"TEAM_RUNTIME_CONFIG = {_py_literal(runtime_config)}",
        "",
        *body_lines,
        "",
        "def build_team():",
        "    return build_team_design().build()",
    ]
    return "\n".join(line for line in module_lines if line is not None).strip() + "\n"


def _render_team_role_helper(dsl: StudioDslDocument, node: StudioCanvasNode, helper_name: str) -> str:
    tool_bindings = list(node.config.get("tool_bindings", []))
    knowledge_bindings = list(node.config.get("knowledge_bindings", []))
    knowledge_scope = _merged_knowledge_scope(dsl, knowledge_bindings)
    runtime_config = _runtime_config_payload(
        dsl,
        reasoning=node.config.get("reasoning"),
        knowledge_scope=knowledge_scope,
        include_max_steps=False,
    )
    model_binding = node.config.get("model_binding") or _default_model_binding_name(dsl)
    return dedent(
        f"""
        def {helper_name}() -> AgentDesign:
            tool_bindings = {_py_literal(tool_bindings)}
            knowledge_bindings = {_py_literal(knowledge_bindings)}
            tool_bundles = build_tool_bundles(tool_bindings)
            unresolved = unresolved_tool_names(tool_bindings)
            if unresolved:
                print("未自动装配的自定义工具，请按需补充：", ", ".join(unresolved))
            knowledge_paths = resolve_knowledge_paths(knowledge_bindings)
            knowledge_scope = resolve_knowledge_scope(knowledge_bindings)
            return AgentDesign(
                name={_quoted(str(node.config.get("agent_name") or node.name or node.id))},
                description={_quoted(node.config.get("description"))},
                profile={_quoted(str(node.config.get("profile", "default")))},
                model=resolve_model_binding({_quoted(model_binding)}) if {_quoted(model_binding)} else None,
                system_prompt={_quoted(node.config.get("system_prompt"))},
                enable_tools=True if tool_bindings else None,
                tool_bundles=tool_bundles,
                enable_rag=True if knowledge_bindings else None,
                knowledge_paths=knowledge_paths or None,
                knowledge_scope=knowledge_scope or None,
                reasoning={_py_literal(node.config.get("reasoning"))},
                context_policy={_py_literal(dsl.runtime.policies.get("context_policy"))},
                state_policy={_py_literal(dsl.runtime.policies.get("state_policy"))},
                coordination_policy={_py_literal(dsl.runtime.policies.get("coordination_policy"))},
                memory_policy={_py_literal(dsl.runtime.policies.get("memory_policy"))},
                runtime_config={_py_literal(runtime_config)},
            )
        """
    ).strip()


def _render_workflow_roles_module(compiled: StudioCompiledArtifact) -> str:
    dsl = compiled.dsl
    role_nodes = [node for node in dsl.canvas.nodes if node.kind == "sub_agent"]
    helper_blocks: list[str] = []
    payload_lines: list[str] = ["def build_role_payloads() -> list[dict[str, Any]]:", "    payloads: list[dict[str, Any]] = []"]
    for node in role_nodes:
        helper_name = f"build_{_safe_identifier(node.id)}_role_design"
        helper_blocks.append(_render_workflow_role_helper(dsl, node, helper_name))
        payload_lines.append(f"    payloads.append({helper_name}().as_role_payload())")
    payload_lines.append("    return payloads")
    helper_text = "\n\n".join(helper_blocks)
    payload_text = "\n".join(payload_lines)
    return dedent(
        f"""
        from __future__ import annotations

        from typing import Any

        from agentorch import AgentDesign, RoleDesign
        from app.bindings.knowledge import resolve_knowledge_paths, resolve_knowledge_scope
        from app.bindings.models import resolve_model_binding
        from app.bindings.tools import build_tool_bundles, unresolved_tool_names

        {helper_text}


        {payload_text}
        """
    ).strip() + "\n"


def _render_workflow_role_helper(dsl: StudioDslDocument, node: StudioCanvasNode, helper_name: str) -> str:
    tool_bindings = list(node.config.get("tool_bindings", []))
    knowledge_bindings = list(node.config.get("knowledge_bindings", []))
    knowledge_scope = _merged_knowledge_scope(dsl, knowledge_bindings)
    runtime_config = _runtime_config_payload(
        dsl,
        reasoning=node.config.get("reasoning"),
        knowledge_scope=knowledge_scope,
        include_max_steps=False,
    )
    model_binding = node.config.get("model_binding") or _default_model_binding_name(dsl)
    design_literal = dedent(
        f"""
        AgentDesign(
            name={_quoted(str(node.config.get("agent_name") or node.name or node.id))},
            description={_quoted(node.config.get("description"))},
            profile={_quoted(str(node.config.get("profile", "default")))},
            model=resolve_model_binding({_quoted(model_binding)}) if {_quoted(model_binding)} else None,
            system_prompt={_quoted(node.config.get("system_prompt"))},
            enable_tools=True if tool_bindings else None,
            tool_bundles=tool_bundles,
            enable_rag=True if knowledge_bindings else None,
            knowledge_paths=knowledge_paths or None,
            knowledge_scope=knowledge_scope or None,
            reasoning={_py_literal(node.config.get("reasoning"))},
            context_policy={_py_literal(dsl.runtime.policies.get("context_policy"))},
            state_policy={_py_literal(dsl.runtime.policies.get("state_policy"))},
            coordination_policy={_py_literal(dsl.runtime.policies.get("coordination_policy"))},
            memory_policy={_py_literal(dsl.runtime.policies.get("memory_policy"))},
            runtime_config={_py_literal(runtime_config) or 'None'},
        )
        """
    ).strip()
    return dedent(
        f"""
        def {helper_name}() -> RoleDesign:
            tool_bindings = {_py_literal(tool_bindings)}
            knowledge_bindings = {_py_literal(knowledge_bindings)}
            tool_bundles = build_tool_bundles(tool_bindings)
            unresolved = unresolved_tool_names(tool_bindings)
            if unresolved:
                print("未自动装配的自定义工具，请按需补充：", ", ".join(unresolved))
            knowledge_paths = resolve_knowledge_paths(knowledge_bindings)
            knowledge_scope = resolve_knowledge_scope(knowledge_bindings)
            return RoleDesign(
                name={_quoted(str(node.config.get("agent_name") or node.name or node.id))},
                role={_quoted(node.config.get("role"))},
                description={_quoted(node.config.get("description"))},
                design={design_literal},
                capabilities={_py_literal(list(node.config.get("capabilities", []) or []))},
                tags={_py_literal(list(node.config.get("tags", []) or []))},
                supports_parallel_tasks={bool(node.config.get("supports_parallel_tasks", False))},
                max_delegation_depth={int(node.config.get("max_delegation_depth", 1) or 1)},
                knowledge_scope=knowledge_scope or None,
            )
        """
    ).strip()


def _render_workflow_module(compiled: StudioCompiledArtifact) -> str:
    dsl = compiled.dsl
    root_model_binding = _workflow_root_model_binding(dsl)
    root_tool_bindings = _workflow_root_tool_bindings(dsl)
    root_knowledge_bindings = _workflow_root_knowledge_bindings(dsl)
    knowledge_scope = _merged_knowledge_scope(dsl, root_knowledge_bindings)
    runtime_config = _runtime_config_payload(dsl, knowledge_scope=knowledge_scope, include_max_steps=False)
    node_lines = [f"        {_render_workflow_node_expression(dsl, node)}," for node in dsl.canvas.nodes if node.kind not in {"start", "end"}]
    edge_lines = [
        f"        Edge(source={_quoted(edge.source)}, target={_quoted(edge.target)}, kind={_quoted(edge.kind)}, condition={_quoted(edge.condition)}),"
        for edge in dsl.canvas.edges
        if _node_kind(dsl, edge.source) != "start" and _node_kind(dsl, edge.target) != "end"
    ]
    entry_node = next(edge.target for edge in dsl.canvas.edges if _node_kind(dsl, edge.source) == "start")
    max_steps = int(dsl.runtime.debug.get("max_steps", 20) or 20)
    shared_knowledge_payload = {
        "knowledge_paths": _knowledge_paths_for_bindings(dsl, root_knowledge_bindings),
        "knowledge_scope": knowledge_scope,
    }
    return dedent(
        f"""
        from __future__ import annotations

        from agentorch.workflow import Edge, Node, Workflow
        from agentorch.studio.runtime import StudioWorkflowRuntimePlan

        from app.bindings.models import resolve_model_binding, split_model_binding
        from app.bindings.tools import build_tool_bundles
        from app.workflows.roles import build_role_payloads

        ROOT_MODEL_BINDING = {_quoted(root_model_binding)}
        ROOT_TOOL_BINDINGS = {_py_literal(root_tool_bindings)}
        ROOT_KNOWLEDGE = {_py_literal(shared_knowledge_payload)}
        WORKFLOW_RUNTIME_CONFIG = {_py_literal(runtime_config)}


        def build_workflow() -> Workflow:
            return Workflow(
                entry_node={_quoted(entry_node)},
                nodes=[
        {"\n".join(node_lines)}
                ],
                edges=[
        {"\n".join(edge_lines)}
                ],
                max_steps={max_steps},
            )


        def build_workflow_plan() -> StudioWorkflowRuntimePlan:
            model_input = resolve_model_binding(ROOT_MODEL_BINDING) if ROOT_MODEL_BINDING else None
            return StudioWorkflowRuntimePlan(
                name={_quoted(dsl.meta.get("name"))},
                description={_quoted(dsl.meta.get("description"))},
                model_config_input=model_input,
                tool_bundles=build_tool_bundles(ROOT_TOOL_BINDINGS),
                shared_knowledge=ROOT_KNOWLEDGE,
                workflow=build_workflow(),
                roles=build_role_payloads(),
                runtime_config=WORKFLOW_RUNTIME_CONFIG or None,
                metadata={{"app_type": "workflow", "entry_node": {_quoted(entry_node)}}},
            )


        def build_workflow_agent():
            return build_workflow_plan().build()
        """
    ).strip() + "\n"


def _render_workflow_node_expression(dsl: StudioDslDocument, node: StudioCanvasNode) -> str:
    config = dict(node.config)
    if node.kind == "llm_agent":
        model_binding = config.get("model_binding") or _default_model_binding_name(dsl)
        prompt = config.pop("prompt", None)
        task_context = config.pop("task_context_from_variables", None)
        goal = config.pop("goal", None)
        output_key = config.pop("output_key", None)
        config.pop("model_binding", None)
        model_name_expr, model_config_expr = _split_model_binding_code(model_binding)
        return (
            f"Node.model_node({_quoted(node.id)}, "
            f"prompt={_py_literal(prompt)}, "
            f"task_context_from_variables={_py_literal(task_context)}, "
            f"model={model_name_expr}, "
            f"model_config={model_config_expr}, "
            f"goal={_py_literal(goal)}, "
            f"output_key={_py_literal(output_key)}, "
            f"**{_py_literal(config)})"
        )
    if node.kind == "tool":
        tool_name = config.pop("tool_name", None)
        arguments = dict(config.pop("arguments", {}))
        if config.get("tool_binding"):
            binding_name = config["tool_binding"]
            binding = next((item for item in dsl.bindings.tools if item.name == binding_name), None)
            if binding is not None and binding.tool_name:
                tool_name = binding.tool_name
        return (
            f"Node.tool({_quoted(node.id)}, {_quoted(str(tool_name or 'custom_tool'))}, "
            f"arguments={_py_literal(arguments)}, **{_py_literal(config)})"
        )
    if node.kind == "router":
        return f"Node(id={_quoted(node.id)}, kind='router', config={_py_literal(config)})"
    if node.kind == "knowledge_retrieve":
        question = config.pop("question", config.pop("query", None))
        output_key = config.pop("output_key", None)
        if config.get("knowledge_bindings") and config.get("knowledge_scope") is None:
            config["knowledge_scope"] = _merged_knowledge_scope(dsl, list(config["knowledge_bindings"]))
        return (
            f"Node.retrieve({_quoted(node.id)}, question={_py_literal(question)}, "
            f"output_key={_py_literal(output_key)}, **{_py_literal(config)})"
        )
    if node.kind == "memory_read":
        return f"Node(id={_quoted(node.id)}, kind='memory', config={_py_literal({'action': 'search', **config})})"
    if node.kind == "memory_write":
        return f"Node(id={_quoted(node.id)}, kind='memory', config={_py_literal({'action': 'remember', **config})})"
    if node.kind == "sub_agent":
        payload = {
            "output_key": config.get("output_key"),
            "reasoning_strategy": config.get("reasoning"),
            "context_policy": dsl.runtime.policies.get("context_policy"),
            "state_policy": dsl.runtime.policies.get("state_policy"),
            "coordination_policy": dsl.runtime.policies.get("coordination_policy"),
            "memory_policy": dsl.runtime.policies.get("memory_policy"),
        }
        knowledge_bindings = list(config.get("knowledge_bindings", []))
        if knowledge_bindings:
            payload["knowledge_scope"] = _merged_knowledge_scope(dsl, knowledge_bindings)
        payload = {key: value for key, value in payload.items() if value is not None}
        return (
            f"Node.agent({_quoted(node.id)}, agent_name={_quoted(str(config.get('agent_name') or node.name or node.id))}, "
            f"input_from_variable={_py_literal(config.get('input_from_variable'))}, "
            f"goal={_py_literal(config.get('goal'))}, **{_py_literal(payload)})"
        )
    if node.kind == "aggregate":
        return (
            f"Node.aggregate({_quoted(node.id)}, sources={_py_literal(list(config.get('sources', [])))}, "
            f"output_key={_py_literal(config.get('output_key'))})"
        )
    if node.kind == "human_input":
        return f"Node(id={_quoted(node.id)}, kind='human_input', config={_py_literal(config)})"
    if node.kind == "human_approval":
        return f"Node(id={_quoted(node.id)}, kind='human_approval', config={_py_literal(config)})"
    return f"Node(id={_quoted(node.id)}, kind={_quoted(node.kind)}, config={_py_literal(config)})"


def _render_smoke_test(compiled: StudioCompiledArtifact) -> str:
    dsl = compiled.dsl
    return dedent(
        f"""
        from __future__ import annotations

        import json
        from pathlib import Path


        def test_exported_project_has_diamond_entry() -> None:
            base = Path(__file__).parents[1]
            app_config = json.loads((base / "configs" / "app.json").read_text(encoding="utf-8"))
            assert app_config["app_type"] == {_quoted(dsl.app_type)}
            assert app_config["diamond_entry"] == "app.diamond:build_diamond"
            assert (base / "app" / "diamond.py").exists()
        """
    ).strip() + "\n"


def _render_agent_snippet(compiled: StudioCompiledArtifact) -> str:
    return "\n".join(
        [
            "from app.agents.main_agent import build_agent",
            "",
            "agent = build_agent()",
            'result = agent.run_sync("hello from exported diamond", thread_id="diamond-sdk-snippet")',
            "print(result.output_text)",
            "agent.close()",
            "",
        ]
    )


def _render_team_snippet(compiled: StudioCompiledArtifact) -> str:
    return "\n".join(
        [
            "from app.teams.main_team import build_team",
            "",
            "system = build_team()",
            'result = system.run_sync("hello from exported diamond", thread_id="diamond-sdk-snippet")',
            "print(result.output_text)",
            "system.close()",
            "",
        ]
    )


def _render_workflow_snippet(compiled: StudioCompiledArtifact) -> str:
    return "\n".join(
        [
            "from app.workflows.main_workflow import build_workflow_agent",
            "",
            "agent = build_workflow_agent()",
            'result = agent.run_sync("hello from exported diamond", thread_id="diamond-sdk-snippet")',
            "print(result.output_text)",
            "agent.close()",
            "",
        ]
    )


def _default_model_binding_name(dsl: StudioDslDocument) -> str | None:
    for binding in dsl.bindings.models:
        if binding.default:
            return binding.name
    return dsl.bindings.models[0].name if dsl.bindings.models else None


def _node_kind(dsl: StudioDslDocument, node_id: str) -> str:
    return next(node.kind for node in dsl.canvas.nodes if node.id == node_id)


def _workflow_root_model_binding(dsl: StudioDslDocument) -> str | None:
    for node in dsl.canvas.nodes:
        if node.kind == "llm_agent" and node.config.get("model_binding"):
            return str(node.config["model_binding"])
    return _default_model_binding_name(dsl)


def _workflow_root_tool_bindings(dsl: StudioDslDocument) -> list[str]:
    values: list[str] = []
    for node in dsl.canvas.nodes:
        if node.kind == "llm_agent":
            values.extend(list(node.config.get("tool_bindings", [])))
        elif node.kind == "tool" and node.config.get("tool_binding"):
            values.append(str(node.config["tool_binding"]))
    return list(dict.fromkeys(values))


def _workflow_root_knowledge_bindings(dsl: StudioDslDocument) -> list[str]:
    values: list[str] = []
    for node in dsl.canvas.nodes:
        if node.kind == "llm_agent":
            values.extend(list(node.config.get("knowledge_bindings", [])))
        elif node.kind == "knowledge_retrieve":
            values.extend(list(node.config.get("knowledge_bindings", [])))
    return list(dict.fromkeys(values))


def _knowledge_paths_for_bindings(dsl: StudioDslDocument, binding_names: list[str]) -> list[str]:
    mapping = {binding.name: binding for binding in dsl.bindings.knowledge_sources}
    paths: list[str] = []
    for binding_name in binding_names:
        binding = mapping.get(binding_name)
        if binding is not None and binding.path is not None:
            paths.append(str(binding.path))
    return list(dict.fromkeys(paths))


def _merged_knowledge_scope(dsl: StudioDslDocument, binding_names: list[str]) -> list[str]:
    mapping = {binding.name: binding for binding in dsl.bindings.knowledge_sources}
    values: list[str] = []
    for binding_name in binding_names:
        binding = mapping.get(binding_name)
        if binding is not None:
            values.extend(binding.scope)
    return list(dict.fromkeys(item for item in values if item))


def _split_model_binding_code(binding_name: str | None) -> tuple[str, str]:
    if binding_name is None:
        return "None", "None"
    return (
        f"split_model_binding({_quoted(binding_name)})[0]",
        f"split_model_binding({_quoted(binding_name)})[1]",
    )


def _safe_identifier(value: str) -> str:
    cleaned = []
    for char in value:
        cleaned.append(char if char.isalnum() else "_")
    identifier = "".join(cleaned).strip("_")
    return identifier or "node"
