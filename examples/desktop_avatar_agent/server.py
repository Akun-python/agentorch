from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

FRAMEWORK_ROOT = Path(__file__).resolve().parents[2]
if str(FRAMEWORK_ROOT) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_ROOT))

from examples.desktop_avatar_agent.agent_service import DesktopAvatarAgentService


DESKTOP_ROOT = Path.home() / "Desktop"
SERVICE = DesktopAvatarAgentService(desktop_root=DESKTOP_ROOT, framework_root=FRAMEWORK_ROOT)


class DesktopAgentHandler(BaseHTTPRequestHandler):
    server_version = "DesktopAvatarAgent/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return {}
        raw = self.rfile.read(content_length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self) -> None:
        self._send_json(HTTPStatus.OK, {"ok": True})

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/health":
            self._send_json(HTTPStatus.OK, SERVICE.health())
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Route not found."})

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        if route != "/chat":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Route not found."})
            return
        try:
            payload = self._read_json_body()
            message = str(payload.get("message", "")).strip()
            if not message:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Field 'message' is required."})
                return
            thread_id = payload.get("thread_id")
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None
            result = SERVICE.chat(message, thread_id=thread_id, metadata=metadata)
            self._send_json(HTTPStatus.OK, result)
        except Exception as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local desktop avatar agent server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DesktopAgentHandler)
    print(f"Desktop avatar agent server listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
