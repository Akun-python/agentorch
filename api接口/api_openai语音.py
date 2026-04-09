import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR / ".env"
OUTPUT_DIR = SCRIPT_DIR / "output"

DEFAULT_BASE_URL = "https://www.dmxapi.cn/v1/audio/speech"
DEFAULT_MODEL = "tts-pro"
DEFAULT_TEXT = "（瞳孔蓝光剧烈。"
DEFAULT_VOICE = "alloy"
DEFAULT_SPEED = 1.0
DEFAULT_RESPONSE_FORMAT = "mp3"
EXTENSION_BY_FORMAT = {
    "mp3": ".mp3",
    "opus": ".opus",
    "aac": ".aac",
    "flac": ".flac",
    "wav": ".wav",
    "pcm": ".pcm",
}


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


def get_config() -> Dict[str, str]:
    load_env_file(ENV_PATH)

    api_key = (os.getenv("OPENAI_TTS_API_KEY") or os.getenv("API_KEY") or "").strip()
    base_url = (os.getenv("OPENAI_TTS_BASE_URL") or DEFAULT_BASE_URL).strip()
    model = (os.getenv("OPENAI_TTS_MODEL") or DEFAULT_MODEL).strip()
    text = (os.getenv("OPENAI_TTS_INPUT") or DEFAULT_TEXT).strip()
    voice = (os.getenv("OPENAI_TTS_VOICE") or DEFAULT_VOICE).strip()
    response_format = (os.getenv("OPENAI_TTS_FORMAT") or DEFAULT_RESPONSE_FORMAT).strip().lower()
    speed = (os.getenv("OPENAI_TTS_SPEED") or str(DEFAULT_SPEED)).strip()

    if not api_key:
        raise ValueError("未找到 API key。请在 .env 中设置 OPENAI_TTS_API_KEY 或 API_KEY。")
    if not text:
        raise ValueError("OPENAI_TTS_INPUT 不能为空。")
    if response_format not in EXTENSION_BY_FORMAT:
        raise ValueError(
            f"OPENAI_TTS_FORMAT 不支持: {response_format}。可选值: {', '.join(EXTENSION_BY_FORMAT)}"
        )

    try:
        speed_value = float(speed)
    except ValueError as exc:
        raise ValueError(f"OPENAI_TTS_SPEED 必须是数字，当前为: {speed}") from exc

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "text": text,
        "voice": voice,
        "speed": str(speed_value),
        "response_format": response_format,
    }


def looks_like_audio(content_type: str, content: bytes) -> bool:
    normalized = content_type.split(";", 1)[0].strip().lower()
    if normalized.startswith("audio/"):
        return True
    if normalized == "application/octet-stream":
        pass

    signatures = (
        b"ID3",
        b"\xff\xfb",
        b"\xff\xf3",
        b"\xff\xf2",
        b"RIFF",
        b"OggS",
        b"fLaC",
    )
    return any(content.startswith(signature) for signature in signatures)


def format_error_response(response: requests.Response) -> str:
    try:
        return json.dumps(response.json(), ensure_ascii=False, indent=2)
    except ValueError:
        content_type = response.headers.get("Content-Type", "")
        if "text" in content_type or "json" in content_type:
            return response.text[:2000]
        preview = response.content[:64].hex(" ")
        return f"非文本响应，Content-Type={content_type or '<empty>'}，前64字节(hex)={preview}"


def save_audio(content: bytes, response_format: str) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    extension = EXTENSION_BY_FORMAT[response_format]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"output_tts_{timestamp}{extension}"
    output_path.write_bytes(content)
    return output_path


def main() -> None:
    config = get_config()

    payload = {
        "model": config["model"],
        "input": config["text"],
        "voice": config["voice"],
        "speed": float(config["speed"]),
        "response_format": config["response_format"],
    }

    print(f"输出目录: {OUTPUT_DIR}")
    print("正在请求语音合成服务...")

    response = requests.post(
        config["base_url"],
        headers={"Authorization": f"Bearer {config['api_key']}"},
        json=payload,
        timeout=60,
    )

    content_type = response.headers.get("Content-Type", "")
    if not response.ok:
        raise RuntimeError(f"接口请求失败: HTTP {response.status_code}\n{format_error_response(response)}")

    if not looks_like_audio(content_type, response.content):
        raise RuntimeError(f"接口返回不是音频\n{format_error_response(response)}")

    output_path = save_audio(response.content, config["response_format"])
    print(f"语音合成成功，已保存到: {output_path}")
    print(f"响应 Content-Type: {content_type or '<empty>'}")


if __name__ == "__main__":
    main()
