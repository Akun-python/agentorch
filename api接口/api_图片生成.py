import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import requests
from requests import Session
from requests.exceptions import ProxyError, RequestException, Timeout


SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR / ".env"

DEFAULT_BASE_URL = "https://api.apiyi.com"
DEFAULT_MODEL = "gemini-3-pro-image-preview"
DEFAULT_PROMPT = "郭靖和杨过抱在一起"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_IMAGE_SIZE = "2K"
DEFAULT_OUTPUT_DIR = "output"
DEFAULT_TIMEOUT = 300
KNOWN_IMAGE_MODELS = (
    "gemini-3-pro-image-preview",
    "gemini-3.1-flash-image-preview",
)


class RetryableServiceError(RuntimeError):
    """Raised when the current model is temporarily unavailable and another model can be tried."""


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


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_csv(value: str | None) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def build_candidate_models(primary_model: str, configured_fallbacks: Iterable[str]) -> List[str]:
    candidates: List[str] = []
    for model in [primary_model, *configured_fallbacks, *KNOWN_IMAGE_MODELS]:
        if model and model not in candidates:
            candidates.append(model)
    return candidates


def build_endpoint(base_url: str, model: str, explicit_url: str) -> str:
    if explicit_url:
        return explicit_url.format(model=model)

    normalized = base_url.rstrip("/")
    if normalized.endswith(":generateContent"):
        return normalized
    if "/models/" in normalized and ":generateContent" not in normalized:
        return f"{normalized}:generateContent"
    if normalized.endswith("/v1beta"):
        return f"{normalized}/models/{model}:generateContent"
    return f"{normalized}/v1beta/models/{model}:generateContent"


def get_config() -> Dict[str, Any]:
    load_env_file(ENV_PATH)

    api_key = os.getenv("APIYI_KEY_image") 
    base_url = (os.getenv("APIYI_GEN_BASE_URL") or DEFAULT_BASE_URL).strip()
    explicit_url = (os.getenv("APIYI_GEN_URL") or "").strip()
    model = (os.getenv("APIYI_GEN_MODEL") or DEFAULT_MODEL).strip()
    prompt = (os.getenv("APIYI_GEN_PROMPT") or DEFAULT_PROMPT).strip()
    aspect_ratio = (os.getenv("APIYI_GEN_ASPECT_RATIO") or DEFAULT_ASPECT_RATIO).strip()
    image_size = (os.getenv("APIYI_GEN_IMAGE_SIZE") or DEFAULT_IMAGE_SIZE).strip()
    output_name = (os.getenv("APIYI_GEN_OUTPUT") or "output_generated").strip()
    output_dir = (os.getenv("APIYI_GEN_OUTPUT_DIR") or DEFAULT_OUTPUT_DIR).strip()
    timeout = int((os.getenv("APIYI_GEN_TIMEOUT") or str(DEFAULT_TIMEOUT)).strip())
    retry_without_proxy = parse_bool(os.getenv("APIYI_GEN_RETRY_WITHOUT_PROXY"), default=True)
    disable_env_proxy = parse_bool(os.getenv("APIYI_GEN_DISABLE_ENV_PROXY"), default=False)
    configured_fallbacks = parse_csv(os.getenv("APIYI_GEN_FALLBACK_MODELS"))

    if not api_key:
        raise ValueError("未找到 APIYI_KEY。请在 .env 中设置 APIYI_KEY。")
    if not prompt:
        raise ValueError("生成提示词不能为空。请设置 APIYI_GEN_PROMPT。")

    return {
        "api_key": api_key,
        "base_url": base_url,
        "explicit_url": explicit_url,
        "candidate_models": build_candidate_models(model, configured_fallbacks),
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "image_size": image_size,
        "output_name": output_name,
        "output_dir": output_dir,
        "timeout": timeout,
        "retry_without_proxy": retry_without_proxy,
        "disable_env_proxy": disable_env_proxy,
    }


def build_payload(config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "contents": [{"parts": [{"text": config["prompt"]}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": config["aspect_ratio"],
                "imageSize": config["image_size"],
            },
        },
    }


def create_session(trust_env: bool) -> Session:
    session = requests.Session()
    session.trust_env = trust_env
    return session


def parse_error_message(data: Dict[str, Any], fallback_text: str) -> str:
    error = data.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return fallback_text.strip()


def raise_for_response(model: str, response: requests.Response) -> Dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        snippet = response.text[:1000]
        raise RuntimeError(
            f"图片生成接口未返回 JSON。模型: {model}，HTTP {response.status_code}，响应片段: {snippet}"
        ) from exc

    if response.ok:
        return data

    message = parse_error_message(data, response.text[:1000])
    details = f"图片生成请求失败。模型: {model}，HTTP {response.status_code}，错误: {message}"

    retryable_markers = ("无可用渠道", "高峰", "繁忙", "overloaded", "temporarily unavailable")
    if response.status_code in {429, 500, 502, 503, 504} or any(marker in message for marker in retryable_markers):
        raise RetryableServiceError(details)

    pretty = json.dumps(data, ensure_ascii=False, indent=2)
    raise RuntimeError(f"{details}\n{pretty}")


def request_once(config: Dict[str, Any], model: str, trust_env: bool) -> Dict[str, Any]:
    endpoint = build_endpoint(config["base_url"], model, config["explicit_url"])
    payload = build_payload(config)

    session = create_session(trust_env=trust_env)
    try:
        response = session.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "x-goog-api-key": config["api_key"],
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=config["timeout"],
        )
    except ProxyError as exc:
        mode = "已禁用环境代理" if not trust_env else "使用环境代理"
        raise ProxyError(f"{mode} 时连接失败: {exc}") from exc
    except Timeout as exc:
        raise RetryableServiceError(
            f"图片生成请求超时。模型: {model}，超时时间: {config['timeout']} 秒。"
        ) from exc
    except RequestException as exc:
        raise RuntimeError(f"图片生成请求异常。模型: {model}，错误: {exc}") from exc
    finally:
        session.close()

    return raise_for_response(model=model, response=response)


def request_image(config: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    trust_env = not config["disable_env_proxy"]

    for model in config["candidate_models"]:
        try:
            data = request_once(config, model=model, trust_env=trust_env)
            data["_used_model"] = model
            data["_used_proxy_mode"] = "disabled" if not trust_env else "env"
            return data
        except ProxyError as exc:
            errors.append(f"{model}: {exc}")
            if trust_env and config["retry_without_proxy"]:
                try:
                    data = request_once(config, model=model, trust_env=False)
                    data["_used_model"] = model
                    data["_used_proxy_mode"] = "disabled-after-proxy-error"
                    return data
                except Exception as retry_exc:  # noqa: BLE001
                    errors.append(f"{model}（禁用代理重试）: {retry_exc}")
            break
        except RetryableServiceError as exc:
            errors.append(str(exc))
            continue

    if errors:
        tips = [
            "1. 在 .env 中指定可用模型，例如 APIYI_GEN_MODEL=gemini-3-pro-image-preview",
            "2. 如果你本机开了代理，先试 APIYI_GEN_DISABLE_ENV_PROXY=1",
            "3. 如果 api.apiyi.com 不稳定，可改成 APIYI_GEN_BASE_URL=https://b.apiyi.com",
        ]
        raise RuntimeError("图片生成失败：\n" + "\n".join(errors) + "\n\n可尝试：\n" + "\n".join(tips))

    raise RuntimeError("图片生成失败，未拿到任何可用响应。")


def extract_image_payload(data: Dict[str, Any]) -> Tuple[str, str]:
    candidates = data.get("candidates")
    if not candidates:
        pretty = json.dumps(data, ensure_ascii=False, indent=2)
        raise RuntimeError(f"接口响应中没有 candidates 字段，完整响应如下：\n{pretty}")

    parts = candidates[0].get("content", {}).get("parts", [])
    for part in parts:
        inline_data = part.get("inlineData")
        if inline_data and inline_data.get("data"):
            mime_type = inline_data.get("mimeType", "image/jpeg")
            return inline_data["data"], mime_type

    pretty = json.dumps(data, ensure_ascii=False, indent=2)
    raise RuntimeError(f"接口已成功返回，但没有找到 inlineData 图片数据，完整响应如下：\n{pretty}")


def extension_from_mime(mime_type: str) -> str:
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    return mapping.get(mime_type.lower(), ".bin")


def save_image(base64_data: str, mime_type: str, output_name: str, output_dir: str) -> Path:
    target = Path(output_name)
    if not target.suffix:
        target = target.with_suffix(extension_from_mime(mime_type))

    if not target.is_absolute():
        target = SCRIPT_DIR / output_dir / target

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(base64.b64decode(base64_data))
    return target


def main() -> None:
    config = get_config()
    data = request_image(config)
    image_data, mime_type = extract_image_payload(data)
    output_path = save_image(
        image_data,
        mime_type,
        output_name=config["output_name"],
        output_dir=config["output_dir"],
    )
    print(f"图片已保存至: {output_path}")
    print(f"图片类型: {mime_type}")
    print(f"使用模型: {data.get('_used_model', 'unknown')}")
    print(f"代理模式: {data.get('_used_proxy_mode', 'unknown')}")


if __name__ == "__main__":
    main()
