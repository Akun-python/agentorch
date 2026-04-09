from openai import OpenAI
import httpx
import sys
from env_utils import get_first_env, load_env_from_script_dir, parse_bool_env

ENV_PATH = load_env_from_script_dir(__file__)
APIYI_KEY_deepseek = get_first_env("APIYI_KEY_deepseek", "APIYI_KEY_DEEPSEEK", "APIYI_KEY", "API_KEY")
DISABLE_ENV_PROXY = parse_bool_env("APIYI_TEXT_DISABLE_ENV_PROXY", default=True)
MODEL_NAME = "deepseek-v3.2-exp"
client = OpenAI(
    api_key=APIYI_KEY_deepseek,
    base_url="https://api.apiyi.com/v1",
    http_client=httpx.Client(trust_env=not DISABLE_ENV_PROXY)
)

stream = client.chat.completions.create(
    model=MODEL_NAME,
    messages=[{"role": "user", "content": "你是什么模型"}],
    stream=True
)

for chunk in stream:
    # 部分流式分片可能不携带 choices，需要先跳过空分片
    if not chunk.choices:
        continue

    if not chunk.choices:
        continue

    delta = chunk.choices[0].delta
    if delta and delta.content is not None:
        output_encoding = sys.stdout.encoding or "utf-8"
        safe_text = delta.content.encode(output_encoding, errors="ignore").decode(output_encoding, errors="ignore")
        print(safe_text, end="", flush=True)
