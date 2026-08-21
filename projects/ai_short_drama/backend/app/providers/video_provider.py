from __future__ import annotations

import base64
import json
import mimetypes
import time
from pathlib import Path

import requests

from projects.ai_short_drama.backend.app.utils.env_loader import get_first_env, parse_bool_env


class SeedanceVideoProvider:
    """封装首帧生视频能力。"""

    def __init__(self) -> None:
        self.api_key = get_first_env("DMXAPI_API_KEY", "OPENAI_VIDEO_API_KEY", "OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("视频能力未配置，请检查 DMXAPI_API_KEY / OPENAI_VIDEO_API_KEY")

        self.url = "https://www.dmxapi.cn/v1/responses"
        self.model = get_first_env("DMXAPI_VIDEO_MODEL", "OPENAI_VIDEO_MODEL", default="doubao-seedance-2-0-260128")
        self.query_model = get_first_env("DMXAPI_VIDEO_QUERY_MODEL", default="seedance-2-0-get")
        self.disable_env_proxy = parse_bool_env("DMXAPI_DISABLE_ENV_PROXY", default=False)
        self.default_resolution = "720p"
        self.default_ratio = "adaptive"
        self.default_duration = 4
        self.default_generate_audio = True
        self.default_return_last_frame = False

    def create_video_task(
        self,
        *,
        prompt: str,
        first_frame_local_path: Path,
        last_frame_local_path: Path | None = None,
        reference_image_local_paths: list[Path] | None = None,
        ratio: str | None = None,
        duration_seconds: int | None = None,
        resolution: str | None = None,
        generate_audio: bool | None = None,
        return_last_frame: bool | None = None,
    ) -> str:
        headers = self._build_headers()
        input_items = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": self._build_image_data_url(first_frame_local_path),
                },
                "role": "first_frame",
            },
        ]
        if last_frame_local_path is not None:
            input_items.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": self._build_image_data_url(last_frame_local_path),
                    },
                    "role": "last_frame",
                }
            )
        for reference_image_path in reference_image_local_paths or []:
            input_items.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": self._build_image_data_url(reference_image_path),
                    },
                    "role": "reference_image",
                }
            )

        payload = {
            "model": self.model,
            "input": input_items,
            "generate_audio": self.default_generate_audio if generate_audio is None else generate_audio,
            "resolution": resolution or self.default_resolution,
            "ratio": ratio or self.default_ratio,
            "duration": duration_seconds or self.default_duration,
            "seed": -1,
            "watermark": False,
            "return_last_frame": self.default_return_last_frame if return_last_frame is None else return_last_frame,
            "execution_expires_after": 172800,
        }

        with self._make_session() as session:
            response = session.post(self.url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()

        result = response.json()
        task_id = result.get("id") or result.get("request_id")
        if not task_id:
            raise RuntimeError(f"视频任务创建成功但未返回任务 ID: {json.dumps(result, ensure_ascii=False)}")
        return task_id

    def wait_for_video_result(self, task_id: str, *, poll_interval_seconds: int = 8, timeout_seconds: int = 600) -> dict:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            response_json = self.query_video_result(task_id)
            parsed = self._extract_video_result(response_json)
            if parsed:
                status = parsed.get("status")
                if status == "succeeded":
                    return parsed
                if status in {"failed", "expired", "canceled"}:
                    raise RuntimeError(f"视频生成失败: {json.dumps(parsed, ensure_ascii=False)}")
            time.sleep(poll_interval_seconds)

        raise TimeoutError(f"视频查询超时，任务 ID: {task_id}")

    def query_video_result(self, task_id: str) -> dict:
        headers = self._build_headers()
        payload = {"model": self.query_model, "input": task_id}
        with self._make_session() as session:
            response = session.post(self.url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()

    def download_video(self, *, video_url: str, output_path: Path) -> Path:
        return self._store_media(video_url, output_path, timeout_seconds=180)

    def download_last_frame(self, *, last_frame_url: str, output_path: Path) -> Path:
        return self._store_media(last_frame_url, output_path, timeout_seconds=120)

    def extract_video_url(self, video_result: dict) -> str | None:
        return self._extract_media_value(video_result, "video_url")

    def extract_last_frame_url(self, video_result: dict) -> str | None:
        for key in ("last_frame_url", "last_frame", "last_frame_image"):
            value = self._extract_media_value(video_result, key)
            if value:
                return value
        return None

    def _build_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _make_session(self) -> requests.Session:
        session = requests.Session()
        session.trust_env = not self.disable_env_proxy
        return session

    def _store_media(self, media_url: str, output_path: Path, *, timeout_seconds: int) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if media_url.startswith("data:"):
            output_path.write_bytes(self._decode_data_url(media_url))
            return output_path

        if not media_url.startswith(("http://", "https://")):
            output_path.write_bytes(self._decode_base64_payload(media_url))
            return output_path

        with self._make_session() as session:
            response = session.get(media_url, stream=True, timeout=timeout_seconds)
            response.raise_for_status()
            with open(output_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 512):
                    if chunk:
                        file.write(chunk)
        return output_path

    @staticmethod
    def _extract_video_result(response_json: dict) -> dict | None:
        output = response_json.get("output") or []
        if not output:
            return None

        try:
            text = output[0]["content"][0]["text"]
            parsed = json.loads(text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            return None

        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _extract_media_value(payload: dict, key: str) -> str | None:
        for container in (payload, payload.get("content"), payload.get("meta_data")):
            if not isinstance(container, dict):
                continue

            value = container.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                for nested_key in ("url", "image_url", "video_url", "data", "base64"):
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, str) and nested_value.strip():
                        return nested_value.strip()
        return None

    @staticmethod
    def _build_image_data_url(image_path: Path) -> str:
        if not image_path.is_file():
            raise FileNotFoundError(f"图片不存在: {image_path}")

        mime_type = mimetypes.guess_type(image_path.name)[0]
        if not mime_type or not mime_type.startswith("image/"):
            raise ValueError(f"无法识别图片格式: {image_path.name}")

        image_base64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        return f"data:{mime_type};base64,{image_base64}"

    @staticmethod
    def _decode_data_url(data_url: str) -> bytes:
        _, _, encoded = data_url.partition(",")
        if not encoded:
            raise ValueError("数据 URL 格式不正确")
        return base64.b64decode(encoded)

    @staticmethod
    def _decode_base64_payload(payload: str) -> bytes:
        try:
            return base64.b64decode(payload, validate=False)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("无法解析尾帧内容为图片数据") from exc
