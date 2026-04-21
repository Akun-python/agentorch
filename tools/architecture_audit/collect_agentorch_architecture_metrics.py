from __future__ import annotations

import argparse
import ast
import json
import subprocess
import tomllib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _git_commit(repo_root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return completed.stdout.strip() or None


def _load_modules(package_root: Path) -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for path in package_root.rglob("*.py"):
        module_name = ".".join(path.relative_to(package_root).with_suffix("").parts)
        modules[module_name] = path
    return modules


def _parse_module(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _resolve_relative_target(module_name: str, node: ast.ImportFrom) -> str | None:
    parts = module_name.split(".")
    parent = parts[:-node.level]
    if node.module:
        parent += node.module.split(".")
    if not parent:
        return None
    return ".".join(parent)


def _build_import_graph(package_root: Path) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    modules = _load_modules(package_root)
    imports_out: dict[str, set[str]] = defaultdict(set)
    imports_in: dict[str, set[str]] = defaultdict(set)

    for module_name, path in modules.items():
        tree = _parse_module(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            target: str | None = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("agentorch."):
                        target = alias.name.split("agentorch.", 1)[1]
                        if target in modules:
                            imports_out[module_name].add(target)
                            imports_in[target].add(module_name)
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    target = _resolve_relative_target(module_name, node)
                elif node.module and node.module.startswith("agentorch."):
                    target = node.module.split("agentorch.", 1)[1]
                if target and target in modules:
                    imports_out[module_name].add(target)
                    imports_in[target].add(module_name)

    return (
        {module: sorted(targets) for module, targets in imports_out.items()},
        {module: sorted(targets) for module, targets in imports_in.items()},
    )


def _strongly_connected_components(graph: dict[str, list[str]]) -> list[list[str]]:
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []
    counter = 0

    def strongconnect(node: str) -> None:
        nonlocal counter
        index[node] = counter
        lowlink[node] = counter
        counter += 1
        stack.append(node)
        on_stack.add(node)

        for child in graph.get(node, []):
            if child not in index:
                strongconnect(child)
                lowlink[node] = min(lowlink[node], lowlink[child])
            elif child in on_stack:
                lowlink[node] = min(lowlink[node], index[child])

        if lowlink[node] == index[node]:
            component: list[str] = []
            while True:
                child = stack.pop()
                on_stack.remove(child)
                component.append(child)
                if child == node:
                    break
            if len(component) > 1:
                components.append(sorted(component))

    for node in graph:
        if node not in index:
            strongconnect(node)

    components.sort(key=lambda values: (-len(values), values))
    return components


def _top_entries(mapping: dict[str, list[str]], *, limit: int = 20) -> list[dict[str, Any]]:
    entries = [{"module": module, "count": len(values), "values": values} for module, values in mapping.items()]
    entries.sort(key=lambda item: (-item["count"], item["module"]))
    return entries[:limit]


def _all_length(path: Path) -> int | None:
    tree = _parse_module(path)
    if tree is None:
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__" and isinstance(node.value, (ast.List, ast.Tuple)):
                    return len(node.value.elts)
    return None


def _top_level_calls(path: Path) -> list[dict[str, Any]]:
    tree = _parse_module(path)
    if tree is None:
        return []
    calls: list[dict[str, Any]] = []
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            else:
                name = "<call>"
            calls.append({"line": node.lineno, "name": name})
    return calls


def _pytest_config(repo_root: Path) -> dict[str, Any]:
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return {"present": False}
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    options = data.get("tool", {}).get("pytest", {}).get("ini_options", {})
    return {
        "present": bool(options),
        "norecursedirs": list(options.get("norecursedirs", [])),
        "testpaths": list(options.get("testpaths", [])),
    }


def collect_metrics(repo_root: Path) -> dict[str, Any]:
    package_root = repo_root / "agentorch"
    imports_out, imports_in = _build_import_graph(package_root)
    key_files = [
        "__init__.py",
        "facade.py",
        "_facade_support.py",
        "runtime/runtime.py",
        "runtime/agent.py",
        "runtime/context_kernel.py",
        "runtime/context_compaction.py",
        "strategies.py",
        "config/settings.py",
        "models/__init__.py",
        "evolution/session.py",
    ]
    line_counts = {
        rel_path: _line_count(package_root / rel_path)
        for rel_path in key_files
        if (package_root / rel_path).exists()
    }
    root_init = package_root / "__init__.py"
    models_init = package_root / "models" / "__init__.py"
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "package_root": str(package_root),
        "git_commit": _git_commit(repo_root),
        "root_public_api": {
            "__all__": _all_length(root_init),
            "line_count": _line_count(root_init),
            "top_level_calls": _top_level_calls(root_init),
        },
        "line_counts": line_counts,
        "top_import_fan_in": _top_entries(imports_in),
        "top_import_fan_out": _top_entries(imports_out),
        "cycles": _strongly_connected_components(imports_out),
        "import_time_registration": {
            "models_init_top_level_calls": _top_level_calls(models_init),
        },
        "pytest_config": _pytest_config(repo_root),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect reproducible AgentTorch architecture metrics.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root containing the agentorch package.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "artifacts" / "agentorch_architecture_audit" / "metrics.json",
        help="JSON output path.",
    )
    args = parser.parse_args()

    metrics = collect_metrics(args.repo_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote architecture metrics to {args.output}")


if __name__ == "__main__":
    main()
