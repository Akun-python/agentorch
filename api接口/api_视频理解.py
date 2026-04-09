from openai import OpenAI
import base64
import json
from datetime import datetime
import os
import httpx
from env_utils import get_first_env, load_env_from_script_dir, parse_bool_env, resolve_from_script_dir

#23分钟，0.56元

ENV_PATH = load_env_from_script_dir(__file__)

API_URL = "https://api.apiyi.com/v1"
API_KEY = get_first_env("APIYI_KEY_ROLE", "APIYI_KEY", "API_KEY")
DISABLE_ENV_PROXY = parse_bool_env("APIYI_VIDEO_DISABLE_ENV_PROXY", default=True)
VIDEO_PATH = r"C:\Users\24260\Desktop\研究生生涯\slides_video.mp4"  # 本地文件，≤20 MB 为佳
DEFAULT_MODEL = "gemini-2.5-flash"

def gemini_test(question, model=DEFAULT_MODEL):
    if not API_KEY:
        raise ValueError(f"未读取到 API Key，请检查 {ENV_PATH} 中的 APIYI_KEY_ROLE、APIYI_KEY 或 API_KEY 配置")

    client = OpenAI(
        api_key=API_KEY,
        base_url=API_URL,
        http_client=httpx.Client(trust_env=not DISABLE_ENV_PROXY)
    )
    model = model
    user_msg = question

    video_path = VIDEO_PATH if os.path.isabs(VIDEO_PATH) else resolve_from_script_dir(__file__, VIDEO_PATH)
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"未找到视频文件：{video_path}，请检查 VIDEO_PATH 配置是否正确")

    with open(video_path, "rb") as f:
        video_b64 = base64.b64encode(f.read()).decode()
        video_url = f"data:video/mp4;base64,{video_b64}"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": video_url
                        },
                        "mime_type": "video/mp4",
                    }
                ]
            }
        ],
        temperature=0.2,
        max_tokens=4096
    )

    return response.choices[0].message.content

if __name__ == "__main__":
    print("开始视频理解测试...")

    #{/* 运行视频理解 */}
    question = "请描述这个视频的内容"
    result = gemini_test(question)

    #{/* 生成时间戳 */}
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    #{/* 获取当前脚本所在目录 */}
    current_dir = os.path.dirname(os.path.abspath(__file__))

    #{/* 保存为txt文件 */}
    txt_filename = os.path.join(current_dir, f"video_analysis_{timestamp}.txt")
    with open(txt_filename, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("视频理解分析结果\n")
        f.write("=" * 60 + "\n")
        f.write(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"提问内容: {question}\n")
        f.write("=" * 60 + "\n\n")
        f.write(result)
        f.write("\n\n" + "=" * 60 + "\n")

    #{/* 保存为json文件 */}
    json_filename = os.path.join(current_dir, f"video_analysis_{timestamp}.json")
    data = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "question": question,
        "model": DEFAULT_MODEL,
        "video_file": VIDEO_PATH,
        "result": result
    }
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    #{/* 控制台输出 */}
    print("\n视频理解结果：")
    print(result)
    print(f"\n结果已保存到:")
    print(f"  - TXT文件: {txt_filename}")
    print(f"  - JSON文件: {json_filename}")
