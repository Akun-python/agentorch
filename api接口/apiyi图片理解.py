import argparse
import base64
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict

import requests

model_image2tex = ["gemini-2.5-pro","gpt-4o"]
DEFAULT_BASE_URL = "https://api.apiyi.com/v1/chat/completions"
DEFAULT_MODEL = model_image2tex[0]
DEFAULT_PROMPT = "分析这张图片中的所有文字内容"
SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR / ".env"


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue

        if " #" in value:
            value = value.split(" #", 1)[0].rstrip()

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


def load_config() -> Dict[str, str]:
    load_env_file(ENV_PATH)

    api_key = (os.getenv("APIYI_KEY") or os.getenv("API_KEY") or "").strip()
    base_url = (os.getenv("APIYI_IMAGE_BASEURL") or DEFAULT_BASE_URL).strip()
    model = (os.getenv("APIYI_IMAGE_MODEL") or DEFAULT_MODEL).strip()
    prompt = (os.getenv("APIYI_IMAGE_PROMPT") or DEFAULT_PROMPT).strip()
    image_path = (os.getenv("APIYI_IMAGE_PATH") or "").strip()

    if not api_key:
        raise ValueError("未找到 API key。请在 .env 中设置 APIYI_KEY，或提供可复用的 API_KEY。")

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "prompt": prompt,
        "image_path": image_path,
    }


def image_to_data_url(image_path: Path) -> str:
    if not image_path.exists():
        raise FileNotFoundError(f"图片不存在: {image_path}")

    mime_type, _ = mimetypes.guess_type(image_path.name)
    mime_type = mime_type or "application/octet-stream"

    with image_path.open("rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("utf-8")

    return f"data:{mime_type};base64,{encoded}"


def extract_text(response_json: Dict[str, Any]) -> str:
    choices = response_json.get("choices") or []
    if not choices:
        return str(response_json)

    message = choices[0].get("message") or {}
    content = message.get("content")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if text:
                    parts.append(text)
        if parts:
            return "\n".join(parts)

    return str(response_json)


def parse_args(default_image_path: str, default_prompt: str, default_model: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="调用 apiyi 图片理解接口")
    parser.add_argument("--image", default=default_image_path, help="本地图片路径，默认读取 .env 中的 APIYI_IMAGE_PATH")
    parser.add_argument("--prompt", default=default_prompt, help="提问内容，默认读取 .env 中的 APIYI_IMAGE_PROMPT")
    parser.add_argument("--model", default=default_model, help="模型名，默认读取 .env 中的 APIYI_IMAGE_MODEL")
    return parser.parse_args()


def main() -> None:
    config = load_config()
    args = parse_args(config["image_path"], config["prompt"], config["model"])

    if not args.image:
        raise ValueError("未提供图片路径。请传入 --image，或在 .env 中设置 APIYI_IMAGE_PATH。")

    image_path = Path(args.image).expanduser()
    if not image_path.is_absolute():
        image_path = SCRIPT_DIR / image_path
    data_url = image_to_data_url(image_path)

    payload = {
        "model": args.model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": args.prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    }

    response = requests.post(
        config["base_url"],
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    response.raise_for_status()

    print(extract_text(response.json()))


if __name__ == "__main__":
    main()
