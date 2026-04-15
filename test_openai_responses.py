from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI


DEFAULT_BASE_URL = "http://192.168.31.36:8080"
DEFAULT_MODEL = "gpt-5.4"
DEFAULT_PROMPT = "Reply with exactly: OK"
DEFAULT_PROMPTS = [
    DEFAULT_PROMPT,
    "What is 13 + 29? Reply with digits only.",
    "Name the capital of France in one word.",
    'Return strict JSON only: {"status":"ok"}',
    "请只回复：测试成功",
]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def get_field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def shorten(text: str, limit: int = 800) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def format_error(exc: Exception) -> str:
    parts = [f"{exc.__class__.__name__}: {exc}"]
    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        parts.append(f"status_code={status_code}")
    response = getattr(exc, "response", None)
    if response is not None:
        response_status = getattr(response, "status_code", None)
        if response_status is not None and response_status != status_code:
            parts.append(f"response_status={response_status}")
        request = getattr(response, "request", None)
        if request is not None:
            parts.append(f"request={request.method} {request.url}")
        try:
            body = response.text
        except Exception:
            body = ""
        if body:
            parts.append(f"response_body={shorten(body)}")
    return "\n".join(parts)


def extract_responses_text(response: Any) -> str:
    direct_text = get_field(response, "output_text")
    if direct_text:
        return str(direct_text).strip()

    pieces: list[str] = []
    for item in get_field(response, "output", []) or []:
        if get_field(item, "type") != "message":
            continue
        for content in get_field(item, "content", []) or []:
            content_type = get_field(content, "type")
            if content_type in {"output_text", "text"}:
                text = get_field(content, "text") or get_field(content, "value")
                if text:
                    pieces.append(str(text))
    return "".join(pieces).strip()


def extract_usage(response: Any) -> dict[str, Any]:
    usage = get_field(response, "usage")
    if not usage:
        return {}
    keys = (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
    )
    data = {key: get_field(usage, key) for key in keys}
    return {key: value for key, value in data.items() if value is not None}


def build_client(base_url: str, api_key: str, timeout: float) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)


def load_prompts_from_file(path: Path) -> list[str]:
    prompts: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        prompts.append(line)
    return prompts


def resolve_prompts(args: argparse.Namespace) -> list[str]:
    prompts: list[str] = []
    if args.prompts_file:
        prompts.extend(load_prompts_from_file(Path(args.prompts_file)))
    if args.prompts:
        prompts.extend(args.prompts)
    if not prompts:
        prompts.extend(DEFAULT_PROMPTS)
    return prompts


def add_usage_totals(target: dict[str, int], usage: dict[str, Any]) -> None:
    for key, value in usage.items():
        if isinstance(value, int):
            target[key] = target.get(key, 0) + value


def test_responses_api(client: OpenAI, model: str, prompt: str, max_output_tokens: int) -> dict[str, Any]:
    response = client.responses.create(
        model=model,
        input=prompt,
        max_output_tokens=max_output_tokens,
        store=False,
    )
    return {
        "id": get_field(response, "id"),
        "text": extract_responses_text(response),
        "usage": extract_usage(response),
    }


def test_chat_completions_api(client: OpenAI, model: str, prompt: str, max_output_tokens: int) -> dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_output_tokens,
    )
    choice = response.choices[0]
    message = get_field(choice, "message")
    usage = get_field(response, "usage")
    usage_data = {
        key: get_field(usage, key)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if get_field(usage, key) is not None
    }
    return {
        "id": get_field(response, "id"),
        "text": (get_field(message, "content") or "").strip(),
        "usage": usage_data,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test whether an OpenAI-compatible endpoint works with the Responses API."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"API base URL. Default: {DEFAULT_BASE_URL}")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model name. Default: {DEFAULT_MODEL}")
    parser.add_argument(
        "--prompt",
        action="append",
        dest="prompts",
        help="Repeat this option to add one or more prompts. If omitted, a built-in multi-prompt suite is used.",
    )
    parser.add_argument(
        "--prompts-file",
        default=None,
        help="Optional UTF-8 text file containing one prompt per line.",
    )
    parser.add_argument("--api-key", default=None, help="API key. Defaults to OPENAI_API_KEY.")
    parser.add_argument("--timeout", type=float, default=60.0, help="Request timeout in seconds.")
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=64,
        help="Upper bound for generated tokens in the test request.",
    )
    parser.add_argument(
        "--dotenv",
        default=".env",
        help="Optional .env file to load before reading environment variables. Default: .env",
    )
    parser.add_argument(
        "--no-chat-diagnosis",
        action="store_true",
        help="Do not run a chat.completions fallback request when the Responses API fails.",
    )
    parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Stop immediately after the first failed Responses API case.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(Path(args.dotenv))
    prompts = resolve_prompts(args)

    api_key = "sk-47b1dc92e7f7a4d975a77e997f80800ac0d86dc16819b89727f12c1c356f82c9"
    if not api_key:
        print("Missing API key. Set OPENAI_API_KEY or pass --api-key.", file=sys.stderr)
        return 2

    client = build_client(base_url=args.base_url, api_key=api_key, timeout=args.timeout)
    try:
        total_usage: dict[str, int] = {}
        success_count = 0
        failed_indices: list[int] = []

        print(f"Running {len(prompts)} prompt test(s) against {args.base_url} with model={args.model}")
        for index, prompt in enumerate(prompts, start=1):
            print(f"\n=== Case {index}/{len(prompts)} ===")
            print(f"prompt={prompt!r}")
            try:
                responses_result = test_responses_api(
                    client=client,
                    model=args.model,
                    prompt=prompt,
                    max_output_tokens=args.max_output_tokens,
                )
                print("SUCCESS: Responses API request completed.")
                print(f"response_id={responses_result['id']}")
                print(f"output={responses_result['text']!r}")
                if responses_result["usage"]:
                    print(f"usage={responses_result['usage']}")
                    add_usage_totals(total_usage, responses_result["usage"])
                success_count += 1
                continue
            except Exception as exc:
                print("FAILED: Responses API request did not complete.")
                print(format_error(exc))

            failed_indices.append(index)
            if not args.no_chat_diagnosis:
                try:
                    print("[diagnosis] Testing chat.completions for the same prompt")
                    chat_result = test_chat_completions_api(
                        client=client,
                        model=args.model,
                        prompt=prompt,
                        max_output_tokens=args.max_output_tokens,
                    )
                    print("chat.completions succeeded.")
                    print(f"response_id={chat_result['id']}")
                    print(f"output={chat_result['text']!r}")
                    if chat_result["usage"]:
                        print(f"usage={chat_result['usage']}")
                    print('DIAGNOSIS: auth/network/model are likely OK, but this endpoint is not compatible with wire_api="responses" for this case.')
                except Exception as exc:
                    print("chat.completions also failed.")
                    print(format_error(exc))
                    if not args.base_url.rstrip("/").endswith("/v1"):
                        print('TIP: if you see 404 or 405 errors, try base_url ending with "/v1".')

            if args.stop_on_failure:
                break

        print("\n=== Summary ===")
        print(f"responses_success={success_count}/{len(prompts)}")
        print(f"responses_failed={len(failed_indices)}")
        if failed_indices:
            print(f"failed_cases={failed_indices}")
        if total_usage:
            print(f"responses_usage_total={total_usage}")
        return 0 if not failed_indices else 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
