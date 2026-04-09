#!/usr/bin/env python3
import requests
import base64
import os
import json
from datetime import datetime
from env_utils import get_first_env, load_env_from_script_dir, parse_bool_env

ENV_PATH = load_env_from_script_dir(__file__)
APIYI_KEY_image = get_first_env("APIYI_KEY_image", "APIYI_KEY_IMAGE", "APIYI_KEY", "API_KEY")
DISABLE_ENV_PROXY = parse_bool_env("APIYI_NANOBANANA_DISABLE_ENV_PROXY", default=True)
class GeminiImageGenerator:
    """Gemini 图片生成器（谷歌原生格式）"""

    SUPPORTED_ASPECT_RATIOS = [
        "21:9", "16:9", "4:3", "3:2", "1:1",
        "9:16", "3:4", "2:3", "5:4", "4:5"
    ]

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.apiyi.com/v1beta/models/gemini-3-pro-image-preview:generateContent"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "x-goog-api-key": api_key,
        }

    def generate_image(self, prompt: str, aspect_ratio: str = "1:1", output_dir: str = "."):
        """生成图片并保存"""
        print(f"开始生成图片...")
        print(f"提示词: {prompt}")
        print(f"纵横比: {aspect_ratio}")
        if not self.api_key:
            return False, f"未读取到 API Key，请检查 {ENV_PATH} 中的 APIYI_KEY_image 配置"

        # 验证纵横比
        if aspect_ratio not in self.SUPPORTED_ASPECT_RATIOS:
            return False, f"不支持的纵横比 {aspect_ratio}"

        # 构建请求
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": aspect_ratio}
            }
        }

        try:
            with requests.Session() as session:
                session.trust_env = not DISABLE_ENV_PROXY
                response = session.post(self.api_url, headers=self.headers, json=payload, timeout=120)

            if response.status_code != 200:
                error_text = response.text[:500] if response.text else "无响应内容"
                return False, f"API 请求失败，状态码: {response.status_code}，响应: {error_text}"

            result = response.json()

            # 兼容返回多个 part 的情况，逐个查找图片数据
            candidates = result.get("candidates", [])
            parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
            image_data = None
            for part in parts:
                inline_data = part.get("inlineData")
                if inline_data and inline_data.get("data"):
                    image_data = inline_data["data"]
                    break

            if not image_data:
                response_preview = json.dumps(result, ensure_ascii=False)[:500]
                return False, f"接口返回成功，但未找到图片数据，响应片段: {response_preview}"

            # 保存图片
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(output_dir, f"gemini_{timestamp}.png")

            decoded_data = base64.b64decode(image_data)
            with open(output_file, 'wb') as f:
                f.write(decoded_data)

            print(f"图片已保存: {output_file}")
            return True, f"成功保存图片: {output_file}"

        except Exception as e:
            return False, f"错误: {str(e)}"


#{/* 使用示例 */}
if __name__ == "__main__":
    API_KEY = APIYI_KEY_image
    PROMPT = "神雕侠侣中的雕兄"
    ASPECT_RATIO = "16:9"  # 可选: 21:9, 16:9, 4:3, 3:2, 1:1, 9:16, 3:4, 2:3, 5:4, 4:5

    generator = GeminiImageGenerator(API_KEY)
    success, message = generator.generate_image(PROMPT, ASPECT_RATIO)

    if success:
        print(f"生成成功：{message}")
    else:
        print(f"生成失败：{message}")
