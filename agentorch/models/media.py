from __future__ import annotations

import base64
import json
import mimetypes
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from agentorch.core import ModelResponse

from .base import BaseModelAdapter

DEFAULT_IMAGE_ASPECT_RATIO = "16:9"
DEFAULT_IMAGE_SIZE = "2K"
DEFAULT_IMAGE_TIMEOUT = 300.0
DEFAULT_IMAGE_OUTPUT_DIR = Path(".agentorch") / "images"
DEFAULT_VIDEO_ANALYSIS_OUTPUT_DIR = Path(".agentorch") / "video_analysis"

IMAGE_EXTENSION_BY_MIME = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class RetryableImageGenerationError(RuntimeError):
    """Raised when another image model or proxy mode should be attempted."""


class ImageGenerationResult(BaseModel):
    output_path: str
    mime_type: str
    bytes_written: int
    model: str
    proxy_mode: str


class ImageGenerationCapableModelAdapter(BaseModelAdapter, ABC):
    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        *,
        aspect_ratio: str | None = None,
        image_size: str | None = None,
        image_model: str | None = None,
        output_path: str | Path | None = None,
    ) -> ImageGenerationResult:
        raise NotImplementedError


class VideoAnalysisCapableModelAdapter(BaseModelAdapter, ABC):
    @abstractmethod
    async def analyze_video(
        self,
        *,
        prompt: str,
        video_path: str | Path | None = None,
        video_url: str | None = None,
        mime_type: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> ModelResponse:
        raise NotImplementedError


def format_media_http_error_response(response: httpx.Response) -> str:
    try:
        return json.dumps(response.json(), ensure_ascii=False, indent=2)
    except ValueError:
        content_type = response.headers.get("Content-Type", "")
        if "text" in content_type or "json" in content_type:
            return response.text[:2000]
        preview = response.content[:64].hex(" ")
        return f"Non-text response, Content-Type={content_type or '<empty>'}, first64(hex)={preview}"


def build_candidate_image_models(primary_model: str, configured_fallbacks: Iterable[str]) -> list[str]:
    candidates: list[str] = []
    for model in [primary_model, *configured_fallbacks]:
        normalized = (model or "").strip()
        if normalized and normalized not in candidates:
            candidates.append(normalized)
    return candidates


def build_image_generation_endpoint(base_url: str | None, model: str, explicit_url: str | None = None) -> str:
    if explicit_url:
        return explicit_url.format(model=model)
    if not base_url or not base_url.strip():
        raise ValueError("Image base URL is required when image_explicit_url is not configured.")

    normalized = base_url.strip().rstrip("/")
    if normalized.endswith(":generateContent"):
        return normalized
    if "/models/" in normalized and ":generateContent" not in normalized:
        return f"{normalized}:generateContent"
    if normalized.endswith("/v1beta"):
        return f"{normalized}/models/{model}:generateContent"
    return f"{normalized}/v1beta/models/{model}:generateContent"


def build_image_generation_payload(prompt: str, *, aspect_ratio: str, image_size: str) -> dict[str, Any]:
    return {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": aspect_ratio,
                "imageSize": image_size,
            },
        },
    }


def parse_image_error_message(data: Mapping[str, Any], fallback_text: str) -> str:
    error = data.get("error")
    if isinstance(error, Mapping):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return fallback_text.strip()


def ensure_image_generation_success(model: str, response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        snippet = response.text[:1000]
        raise RuntimeError(
            f"Image generation endpoint did not return JSON. model={model}, http_status={response.status_code}, response={snippet}"
        ) from exc

    if response.is_success:
        if isinstance(data, dict):
            return data
        raise RuntimeError(f"Image generation endpoint returned a non-object JSON payload for model={model}.")

    message = parse_image_error_message(data if isinstance(data, Mapping) else {}, response.text[:1000])
    details = f"Image generation request failed. model={model}, http_status={response.status_code}, error={message}"
    lowered_message = message.lower()
    retryable_markers = ("temporarily unavailable", "overloaded", "busy", "high load")
    fallback_model_markers = (
        "multi-modal output is not supported",
        "multimodal output is not supported",
        "response modalities",
        "does not support image",
        "unsupported model",
        "model not found",
    )
    if response.status_code in {429, 500, 502, 503, 504} or any(marker in lowered_message for marker in retryable_markers):
        raise RetryableImageGenerationError(details)
    if response.status_code in {400, 404} and any(marker in lowered_message for marker in fallback_model_markers):
        raise RetryableImageGenerationError(details)
    pretty = json.dumps(data, ensure_ascii=False, indent=2)
    raise RuntimeError(f"{details}\n{pretty}")


def extract_inline_image_payload(data: Mapping[str, Any]) -> tuple[str, str]:
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        pretty = json.dumps(data, ensure_ascii=False, indent=2)
        raise RuntimeError(f"Image generation response did not contain candidates.\n{pretty}")

    first_candidate = candidates[0]
    if not isinstance(first_candidate, Mapping):
        raise RuntimeError("Image generation response contains an invalid candidate payload.")
    content = first_candidate.get("content")
    if not isinstance(content, Mapping):
        raise RuntimeError("Image generation candidate is missing content.")
    parts = content.get("parts")
    if not isinstance(parts, list):
        raise RuntimeError("Image generation candidate is missing parts.")

    for part in parts:
        if not isinstance(part, Mapping):
            continue
        inline_data = part.get("inlineData")
        if not isinstance(inline_data, Mapping):
            continue
        encoded = inline_data.get("data")
        if isinstance(encoded, str) and encoded.strip():
            mime_type = str(inline_data.get("mimeType") or "image/jpeg")
            return encoded, mime_type

    pretty = json.dumps(data, ensure_ascii=False, indent=2)
    raise RuntimeError(f"Image generation response succeeded but did not include inlineData.\n{pretty}")


def image_extension_from_mime(mime_type: str) -> str:
    return IMAGE_EXTENSION_BY_MIME.get(mime_type.strip().lower(), ".bin")


def build_default_image_output_path(*, mime_type: str, root: str | Path | None = None) -> Path:
    output_root = Path(root or DEFAULT_IMAGE_OUTPUT_DIR)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_root / f"output_image_{timestamp}{image_extension_from_mime(mime_type)}"


def resolve_image_output_path(
    *,
    output_path: str | Path | None,
    mime_type: str,
    default_root: str | Path | None = None,
) -> Path:
    target = Path(output_path).expanduser() if output_path is not None else build_default_image_output_path(mime_type=mime_type, root=default_root)
    if target.exists() and target.is_dir():
        target = target / build_default_image_output_path(mime_type=mime_type).name
    elif not target.suffix:
        target = target.with_suffix(image_extension_from_mime(mime_type))
    return target.resolve()


def decode_inline_image_bytes(encoded: str) -> bytes:
    try:
        return base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Image generation response contained invalid base64 image data.") from exc


def resolve_local_media_path(path: str | Path, *, label: str) -> Path:
    resolved = Path(path).expanduser()
    if not resolved.is_absolute():
        resolved = Path.cwd() / resolved
    resolved = resolved.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{label} file not found: {resolved}")
    return resolved


def guess_mime_type(path: str | Path, *, default: str) -> str:
    mime_type, _ = mimetypes.guess_type(str(path))
    return mime_type or default


def build_data_url_from_file(
    path: str | Path,
    *,
    mime_type: str | None = None,
    default_mime_type: str = "application/octet-stream",
) -> tuple[str, str, Path]:
    resolved = resolve_local_media_path(path, label="Media")
    selected_mime_type = (mime_type or guess_mime_type(resolved, default=default_mime_type)).strip() or default_mime_type
    encoded = base64.b64encode(resolved.read_bytes()).decode("utf-8")
    return f"data:{selected_mime_type};base64,{encoded}", selected_mime_type, resolved


def resolve_video_reference(
    *,
    video_path: str | Path | None,
    video_url: str | None,
    mime_type: str | None = None,
) -> tuple[str, str, Path | None]:
    if video_url:
        return video_url, (mime_type or "video/mp4"), None
    if video_path is None:
        raise ValueError("video_path and video_url cannot both be empty.")
    return build_data_url_from_file(video_path, mime_type=mime_type, default_mime_type="video/mp4")


def build_default_video_output_base_path(*, root: str | Path | None = None) -> Path:
    output_root = Path(root or DEFAULT_VIDEO_ANALYSIS_OUTPUT_DIR)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_root / f"video_analysis_{timestamp}"


def resolve_video_output_base_path(
    *,
    output_basename: str | Path | None,
    default_root: str | Path | None = None,
) -> Path:
    target = Path(output_basename).expanduser() if output_basename is not None else build_default_video_output_base_path(root=default_root)
    if target.exists() and target.is_dir():
        target = target / build_default_video_output_base_path().name
    if target.suffix:
        target = target.with_suffix("")
    return target.resolve()


def write_video_analysis_outputs(
    *,
    analysis_text: str,
    question: str,
    model: str,
    video_path: str,
    output_basename: str | Path | None = None,
    default_root: str | Path | None = None,
) -> tuple[Path, Path]:
    base = resolve_video_output_base_path(output_basename=output_basename, default_root=default_root)
    base.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    txt_path = base.with_suffix(".txt")
    json_path = base.with_suffix(".json")

    txt_path.write_text(
        "\n".join(
            [
                "=" * 60,
                "Video analysis result",
                "=" * 60,
                f"Timestamp: {timestamp}",
                f"Question: {question}",
                f"Model: {model}",
                f"Video file: {video_path}",
                "=" * 60,
                "",
                analysis_text,
                "",
                "=" * 60,
                "",
            ]
        ),
        encoding="utf-8",
    )
    json_path.write_text(
        json.dumps(
            {
                "timestamp": timestamp,
                "question": question,
                "model": model,
                "video_file": video_path,
                "result": analysis_text,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return txt_path, json_path


def resolve_response_model_name(raw: Any, *, fallback: str) -> str:
    value = getattr(raw, "model", None)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback
