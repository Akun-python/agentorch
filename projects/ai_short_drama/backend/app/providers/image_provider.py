from __future__ import annotations

import base64
import json
from pathlib import Path

import requests

from projects.ai_short_drama.backend.app.utils.env_loader import get_first_env, parse_bool_env


class NanobananaImageProvider:
    """封装 nanobanana 出图能力。"""

    SUPPORTED_ASPECT_RATIOS = {
        "21:9",
        "16:9",
        "4:3",
        "3:2",
        "1:1",
        "9:16",
        "3:4",
        "2:3",
        "5:4",
        "4:5",
    }

    def __init__(self) -> None:
        self.api_key = get_first_env(
            "APIYI_KEY_image",
            "APIYI_KEY_IMAGE",
            "OPENAI_IMAGE_API_KEY",
            "APIYI_KEY",
            "API_KEY",
        )
        self.api_url = "https://api.apiyi.com/v1beta/models/gemini-3-pro-image-preview:generateContent"
        self.disable_env_proxy = parse_bool_env("APIYI_NANOBANANA_DISABLE_ENV_PROXY", default=True)
        if not self.api_key:
            raise ValueError("图片能力未配置，请检查 APIYI_KEY_image / OPENAI_IMAGE_API_KEY")

    def generate_image(self, *, prompt: str, aspect_ratio: str, output_path: Path) -> Path:
        if aspect_ratio not in self.SUPPORTED_ASPECT_RATIOS:
            raise ValueError(f"不支持的图片比例: {aspect_ratio}")

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": aspect_ratio},
            },
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "x-goog-api-key": self.api_key,
        }

        with requests.Session() as session:
            session.trust_env = not self.disable_env_proxy
            response = session.post(self.api_url, headers=headers, json=payload, timeout=120)

        if response.status_code != 200:
            preview = response.text[:500] if response.text else "无响应内容"
            raise RuntimeError(f"图片生成失败，状态码 {response.status_code}，响应: {preview}")

        result = response.json()
        image_data = self._extract_inline_image(result)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(base64.b64decode(image_data))
        return output_path

    @staticmethod
    def _extract_inline_image(response_json: dict) -> str:
        candidates = response_json.get("candidates") or []
        for candidate in candidates:
            parts = candidate.get("content", {}).get("parts", [])
            for part in parts:
                inline_data = part.get("inlineData")
                if inline_data and inline_data.get("data"):
                    return inline_data["data"]

        preview = json.dumps(response_json, ensure_ascii=False)[:500]
        raise RuntimeError(f"接口返回成功，但未找到图片数据，响应片段: {preview}")
