import base64
import json
import os
import time
from pathlib import Path

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR / ".env"
OUTPUT_DIR = SCRIPT_DIR / "output"

DEFAULT_BASE_URL = "https://www.dmxapi.cn/v1/chat/completions"
DEFAULT_VOICE = "mimo_default"
DEFAULT_STYLE = ""
DEFAULT_TEXT = '''（瞳孔'''
DEFAULT_USER_MESSAGE = "一位"
ALLOWED_VOICES = {"mimo_default", "default_zh", "default_en"}


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


def get_config() -> dict:
    load_env_file(ENV_PATH)

    api_key = (os.getenv("MIMO_API_KEY") or os.getenv("API_KEY") or "").strip()
    base_url = (os.getenv("MIMO_BASE_URL") or os.getenv("BASE_URL") or DEFAULT_BASE_URL).strip()
    voice = (os.getenv("MIMO_VOICE") or DEFAULT_VOICE).strip()
    style = (os.getenv("MIMO_STYLE") or DEFAULT_STYLE).strip()
    text = (os.getenv("MIMO_TEXT") or DEFAULT_TEXT).strip()
    user_message = (os.getenv("MIMO_USER_MESSAGE") or DEFAULT_USER_MESSAGE).strip()

    if not api_key:
        raise ValueError("未找到 API_KEY。请在 .env 中设置 API_KEY 或 MIMO_API_KEY。")

    if voice not in ALLOWED_VOICES:
        raise ValueError(
            "MIMO_VOICE 配置无效: "
            f"{voice}。可选值: {', '.join(sorted(ALLOWED_VOICES))}"
        )

    if not text:
        raise ValueError("MIMO_TEXT 不能为空。")

    return {
        "api_key": api_key,
        "base_url": base_url,
        "voice": voice,
        "style": style,
        "text": text,
        "user_message": user_message,
    }


def build_content(style: str, text: str) -> str:
    style_prefix = f"<style>{style}</style>" if style else ""
    return style_prefix + text


def request_tts(config: dict) -> dict:
    payload = {
        "model": "mimo-v2-tts",
        "messages": [
            {"role": "user", "content": config["user_message"]},
            {"role": "assistant", "content": build_content(config["style"], config["text"])},
        ],
        "audio": {"format": "wav", "voice": config["voice"]},
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

    if not response.ok:
        detail = response.text.strip() or "<empty response>"
        raise RuntimeError(f"接口请求失败: HTTP {response.status_code}\n{detail}")

    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"接口返回的不是合法 JSON: {response.text[:500]}") from exc


def extract_audio_bytes(response_json: dict) -> bytes:
    try:
        audio_b64 = response_json["choices"][0]["message"]["audio"]["data"]
    except (KeyError, IndexError, TypeError) as exc:
        preview = json.dumps(response_json, ensure_ascii=False)[:1000]
        raise RuntimeError(f"接口返回中未找到音频数据: {preview}") from exc

    return base64.b64decode(audio_b64)


def save_audio(audio_bytes: bytes) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / f"audio_{time.strftime('%Y%m%d_%H%M%S')}.wav"
    output_path.write_bytes(audio_bytes)
    return output_path


def main() -> None:
    config = get_config()
    response_json = request_tts(config)
    audio_bytes = extract_audio_bytes(response_json)
    output_path = save_audio(audio_bytes)
    print(f"已保存: {output_path}")


if __name__ == "__main__":
    main()
