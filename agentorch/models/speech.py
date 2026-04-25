from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from .base import BaseModelAdapter

DEFAULT_SPEECH_SPEED = 1.0
DEFAULT_SPEECH_RESPONSE_FORMAT = "mp3"
DEFAULT_SPEECH_ENDPOINT_PATH = "/audio/speech"
DEFAULT_SPEECH_OUTPUT_DIR = Path(".agentorch") / "audio"

EXTENSION_BY_FORMAT = {
    "mp3": ".mp3",
    "opus": ".opus",
    "aac": ".aac",
    "flac": ".flac",
    "wav": ".wav",
    "pcm": ".pcm",
}

_AUDIO_SIGNATURES = (
    b"ID3",
    b"\xff\xfb",
    b"\xff\xf3",
    b"\xff\xf2",
    b"RIFF",
    b"OggS",
    b"fLaC",
)


class SpeechSynthesisResult(BaseModel):
    output_path: str
    response_format: str
    content_type: str
    bytes_written: int
    voice: str
    speed: float
    model: str


class SpeechCapableModelAdapter(BaseModelAdapter, ABC):
    @abstractmethod
    async def synthesize_speech(
        self,
        text: str,
        *,
        voice: str | None = None,
        response_format: str | None = None,
        speed: float | int | str | None = None,
        speech_model: str | None = None,
        output_path: str | Path | None = None,
    ) -> SpeechSynthesisResult:
        raise NotImplementedError


def validate_speech_response_format(value: str | None) -> str:
    normalized = (value or DEFAULT_SPEECH_RESPONSE_FORMAT).strip().lower()
    if normalized not in EXTENSION_BY_FORMAT:
        supported = ", ".join(sorted(EXTENSION_BY_FORMAT))
        raise ValueError(f"Unsupported speech response format '{normalized}'. Supported values: {supported}")
    return normalized


def normalize_speech_speed(value: float | int | str | None) -> float:
    if value is None:
        return DEFAULT_SPEECH_SPEED
    try:
        speed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Speech speed must be numeric, got {value!r}.") from exc
    return speed


def looks_like_audio_content(content_type: str, content: bytes) -> bool:
    normalized = content_type.split(";", 1)[0].strip().lower()
    if normalized.startswith("audio/"):
        return True
    if normalized != "application/octet-stream":
        return False
    return any(content.startswith(signature) for signature in _AUDIO_SIGNATURES)


def format_http_error_response(response: httpx.Response) -> str:
    try:
        return json.dumps(response.json(), ensure_ascii=False, indent=2)
    except ValueError:
        content_type = response.headers.get("Content-Type", "")
        if "text" in content_type or "json" in content_type:
            return response.text[:2000]
        preview = response.content[:64].hex(" ")
        return f"Non-text response, Content-Type={content_type or '<empty>'}, first64(hex)={preview}"


def build_default_speech_output_path(
    *,
    response_format: str,
    root: str | Path | None = None,
) -> Path:
    output_root = Path(root or DEFAULT_SPEECH_OUTPUT_DIR)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    extension = EXTENSION_BY_FORMAT[response_format]
    return output_root / f"output_tts_{timestamp}{extension}"


def resolve_speech_output_path(
    *,
    output_path: str | Path | None,
    response_format: str,
    default_root: str | Path | None = None,
) -> Path:
    resolved_format = validate_speech_response_format(response_format)
    target = Path(output_path).expanduser() if output_path is not None else build_default_speech_output_path(response_format=resolved_format, root=default_root)
    if target.exists() and target.is_dir():
        target = target / build_default_speech_output_path(response_format=resolved_format).name
    elif not target.suffix:
        target = target.with_suffix(EXTENSION_BY_FORMAT[resolved_format])
    return target.resolve()
