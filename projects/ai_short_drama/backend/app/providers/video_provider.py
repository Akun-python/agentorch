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

    def create_video_task(
        self,
        *,
        prompt: str,
        first_frame_local_path: Path,
        ratio: str | None = None,
        duration_seconds: int | None = None,
        resolution: str | None = None,
        generate_audio: bool | None = None,
    ) -> str:
        headers = self._build_headers()
        payload = {
            "model": self.model,
            "input": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": self._build_first_frame_image_url(first_frame_local_path),
                    },
                    "role": "first_frame",
                },
            ],
            "generate_audio": self.default_generate_audio if generate_audio is None else generate_audio,
            "resolution": resolution or self.default_resolution,
            "ratio": ratio or self.default_ratio,
            "duration": duration_seconds or self.default_duration,
            "seed": -1,
            "watermark": False,
            "return_last_frame": False,
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
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with self._make_session() as session:
            response = session.get(video_url, stream=True, timeout=180)
            response.raise_for_status()
            with open(output_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 512):
                    if chunk:
                        file.write(chunk)
        return output_path

    def _build_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _make_session(self) -> requests.Session:
        session = requests.Session()
        session.trust_env = not self.disable_env_proxy
        return session

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
    def _build_first_frame_image_url(first_frame_local_path: Path) -> str:
        if not first_frame_local_path.is_file():
            raise FileNotFoundError(f"首帧图不存在: {first_frame_local_path}")

        mime_type = mimetypes.guess_type(first_frame_local_path.name)[0]
        if not mime_type or not mime_type.startswith("image/"):
            raise ValueError(f"无法识别首帧图片格式: {first_frame_local_path.name}")

        image_base64 = base64.b64encode(first_frame_local_path.read_bytes()).decode("utf-8")
        return f"data:{mime_type};base64,{image_base64}"
