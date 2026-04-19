from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import uuid4


def _print_help() -> int:
    print("mock codex cli")
    print("usage: mock_codex_cli.py [-m MODEL] exec --json -C DIR PROMPT")
    return 0


def _parse_args(argv: list[str]) -> tuple[str | None, str, str] | tuple[None, None, None]:
    if not argv or argv[0] in {"-h", "--help", "help"}:
        _print_help()
        return None, None, None
    if argv[0] in {"-V", "--version"}:
        print("codex-cli mock 0.1")
        return None, None, None

    model: str | None = None
    cwd = os.getcwd()
    index = 0

    while index < len(argv):
        token = argv[index]
        if token == "-m" and index + 1 < len(argv):
            model = argv[index + 1]
            index += 2
            continue
        if token == "-c" and index + 1 < len(argv):
            index += 2
            continue
        if token == "-a" and index + 1 < len(argv):
            index += 2
            continue
        if token == "exec":
            index += 1
            break
        index += 1

    if index > len(argv):
        raise SystemExit("missing exec subcommand")

    if index < len(argv) and argv[index] == "resume":
        index += 1
        if index < len(argv) and not argv[index].startswith("-"):
            index += 1

    prompt_parts: list[str] = []
    while index < len(argv):
        token = argv[index]
        if token == "-C" and index + 1 < len(argv):
            cwd = argv[index + 1]
            index += 2
            continue
        if token in {"-s", "-o", "--output-last-message", "--color"} and index + 1 < len(argv):
            index += 2
            continue
        if token in {"--json", "--skip-git-repo-check", "--ephemeral"}:
            index += 1
            continue
        if token.startswith("-"):
            index += 1
            continue
        prompt_parts.append(token)
        index += 1

    prompt = " ".join(prompt_parts).strip() or "(no prompt)"
    return model, cwd, prompt


def _write_artifacts(workspace: Path, *, model: str | None, prompt: str) -> str:
    artifact_path = workspace / "smoke_output.txt"
    artifact_path.write_text(
        "codexharness smoke artifact\n"
        f"model={model or 'unset'}\n"
        f"prompt={prompt}\n",
        encoding="utf-8",
    )

    meta = {
        "model": model,
        "prompt": prompt,
        "cwd": str(workspace),
        "openai_api_key": os.environ.get("OPENAI_API_KEY"),
        "codex_api_key": os.environ.get("CODEXHARNESS_CODEX_API_KEY"),
        "openai_base_url": os.environ.get("OPENAI_BASE_URL"),
        "codex_base_url": os.environ.get("CODEXHARNESS_CODEX_BASE_URL"),
    }
    meta_path = workspace / "codex_mock_meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return artifact_path.name


def _emit_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    model, cwd, prompt = _parse_args(args)
    if cwd is None:
        return 0

    workspace = Path(cwd).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    artifact_name = _write_artifacts(workspace, model=model, prompt=prompt)
    thread_id = f"mock-thread-{uuid4().hex[:8]}"

    _emit_json({"type": "thread.started", "thread_id": thread_id})
    _emit_json({"type": "turn.started"})
    _emit_json(
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": f"Mock Codex created {artifact_name} and codex_mock_meta.json successfully.",
            },
        }
    )
    _emit_json({"type": "turn.completed", "usage": {"output_tokens": 24}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
