from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _build_chat_response(content: str) -> dict[str, object]:
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": 0,
        "model": "mock-model",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": content,
                },
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 10,
            "total_tokens": 20,
        },
    }


def _planner_payload() -> str:
    return json.dumps(
        {
            "tasks": [
                {
                    "goal": "Create a smoke artifact in the workspace.",
                    "acceptance_criteria": [
                        "Create smoke_output.txt in the project root",
                        "Create codex_mock_meta.json describing the mock Codex environment",
                    ],
                    "constraints": ["Avoid unrelated changes."],
                    "expected_output": "Return a short summary of the created artifact files.",
                    "write_scope": ["smoke_output.txt", "codex_mock_meta.json"],
                    "depends_on": [],
                }
            ]
        },
        ensure_ascii=False,
    )


def _review_payload() -> str:
    return json.dumps(
        {
            "decision": "completed",
            "score": 1.0,
            "gap_list": [],
            "evidence": ["Detected changed files and mock codex execution evidence."],
            "next_prompt": "",
            "needs_human": False,
            "summary": "Smoke task completed successfully.",
        },
        ensure_ascii=False,
    )


def _integration_payload() -> str:
    return json.dumps(
        {
            "all_done": True,
            "summary": "All smoke-test tasks completed successfully.",
            "next_actions": [],
        },
        ensure_ascii=False,
    )


class _MockOpenAIHandler(BaseHTTPRequestHandler):
    server_version = "MockOpenAI/0.1"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        payload = json.loads(raw_body.decode("utf-8"))
        messages = payload.get("messages") or []
        content = messages[-1].get("content", "") if messages else ""

        if '"tasks":[' in content or "acceptance_criteria" in content:
            response = _build_chat_response(_planner_payload())
        elif '"decision":"completed|needs_followup|redo|blocked|ask_human"' in content or '"decision"' in content:
            response = _build_chat_response(_review_payload())
        elif '"all_done":false' in content or '"next_actions"' in content:
            response = _build_chat_response(_integration_payload())
        else:
            response = _build_chat_response(_integration_payload())

        encoded = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _start_mock_server(port: int) -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer(("127.0.0.1", port), _MockOpenAIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _run_git(workdir: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(workdir),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _prepare_temp_repo(root: Path) -> None:
    _run_git(root, "init")
    _run_git(root, "config", "user.name", "codexharness-smoke")
    _run_git(root, "config", "user.email", "codexharness-smoke@example.com")
    (root / "README.md").write_text("# smoke repo\n", encoding="utf-8")
    _run_git(root, "add", "README.md")
    _run_git(root, "commit", "-m", "initial smoke commit")


def _run_harness(temp_repo: Path, env_file: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = ".;./src"
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        env.pop(key, None)
    env["NO_PROXY"] = "127.0.0.1,localhost"
    env["no_proxy"] = "127.0.0.1,localhost"
    command = [
        "py",
        "-3.13",
        "-m",
        "codexharness",
        "run",
        "--project-root",
        str(temp_repo),
        "--workspace-mode",
        "shared",
        "--env-file",
        str(env_file),
        "--prompt",
        "Run the local codexharness smoke test.",
        "--max-rounds",
        "2",
        "--planner-max-tasks",
        "1",
        "--max-parallel-tasks",
        "1",
        "--codex-binary",
        str(REPO_ROOT / "scripts" / "mock_codex.cmd"),
    ]
    return subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        env=env,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local offline codexharness smoke test.")
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep the temporary git workspace so you can inspect smoke_output.txt and codex_mock_meta.json afterwards.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    port = _find_free_port()
    server, thread = _start_mock_server(port)
    temp_dir = Path(tempfile.mkdtemp(prefix="codexharness-smoke-"))

    try:
        temp_repo = temp_dir / "project"
        temp_repo.mkdir(parents=True, exist_ok=True)
        _prepare_temp_repo(temp_repo)

        env_file = temp_dir / ".env"
        env_file.write_text(
            "\n".join(
                [
                    "CODEXHARNESS_MODEL_NAME=mock-harness-model",
                    f"CODEXHARNESS_BASE_URL=http://127.0.0.1:{port}/v1",
                    "CODEXHARNESS_API_KEY=sk-harness-test",
                    "CODEXHARNESS_CODEX_MODEL_NAME=mock-codex-model",
                    f"CODEXHARNESS_CODEX_BASE_URL=http://127.0.0.1:{port}/v1",
                    "CODEXHARNESS_CODEX_API_KEY=sk-codex-test",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        result = _run_harness(temp_repo, env_file)
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            raise SystemExit(f"Smoke test failed: codexharness exited with code {result.returncode}")

        data = json.loads(result.stdout)
        if data.get("overall_status") != "completed":
            raise SystemExit(f"Smoke test failed: overall_status={data.get('overall_status')!r}")

        artifact_path = temp_repo / "smoke_output.txt"
        meta_path = temp_repo / "codex_mock_meta.json"
        if not artifact_path.exists():
            raise SystemExit("Smoke test failed: smoke_output.txt was not created.")
        if not meta_path.exists():
            raise SystemExit("Smoke test failed: codex_mock_meta.json was not created.")

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("model") != "mock-codex-model":
            raise SystemExit(f"Smoke test failed: unexpected codex model {meta.get('model')!r}")
        if meta.get("openai_api_key") != "sk-codex-test":
            raise SystemExit("Smoke test failed: child Codex API key was not injected correctly.")

        print("Smoke test passed.")
        print(f"Final run id: {data.get('run_id')}")
        print("Created files: smoke_output.txt, codex_mock_meta.json")
        if args.keep_temp:
            print(f"Kept temporary project: {temp_repo}")
        else:
            print("Temporary project has been cleaned up. Re-run with --keep-temp to inspect artifacts.")
        return 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        if not args.keep_temp and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
