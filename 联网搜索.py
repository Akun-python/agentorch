from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agentorch.tools import ToolError, ToolRegistry, create_brave_search_tool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="使用 Brave Search 进行联网搜索。")
    parser.add_argument("query", nargs="?", default="多智能体系统 最新研究进展", help="要搜索的查询词")
    parser.add_argument("--count", type=int, default=5, help="返回结果数，范围 1-20")
    parser.add_argument("--country", default="CN", help="国家代码，例如 CN、US")
    parser.add_argument("--search-lang", default="zh-hans", help="搜索语言，例如 zh-hans、en")
    parser.add_argument(
        "--safesearch",
        default="moderate",
        choices=["strict", "moderate", "off"],
        help="安全搜索级别",
    )
    parser.add_argument("--freshness", default=None, help="时效过滤，例如 pd、pw、pm、py")
    parser.add_argument("--raw", action="store_true", help="打印完整原始响应")
    return parser.parse_args()


async def run_search(args: argparse.Namespace) -> dict:
    registry = ToolRegistry.empty()
    registry.register(create_brave_search_tool())
    result = await registry.execute(
        "brave_search",
        {
            "query": args.query,
            "count": args.count,
            "country": args.country,
            "search_lang": args.search_lang,
            "safesearch": args.safesearch,
            "freshness": args.freshness,
        },
    )
    return result.data


def print_summary(payload: dict, *, show_raw: bool) -> None:
    results = payload.get("results", [])
    print(f"query: {payload.get('query')}")
    print(f"total_results: {payload.get('total_results', len(results))}")
    print()

    if not results:
        print("没有检索到结果。")
        return

    for index, item in enumerate(results, start=1):
        print(f"{index}. {item.get('title') or '(无标题)'}")
        print(f"   url: {item.get('url')}")
        if item.get("description"):
            print(f"   snippet: {item.get('description')}")
        if item.get("age"):
            print(f"   age: {item.get('age')}")
        if item.get("language"):
            print(f"   language: {item.get('language')}")
        print()

    if show_raw:
        print("raw:")
        print(json.dumps(payload.get("raw", {}), ensure_ascii=False, indent=2))


async def amain() -> int:
    args = parse_args()
    try:
        payload = await run_search(args)
    except ToolError as exc:
        message = str(exc)
        print(f"Brave 搜索失败: {message}")
        if "API key is missing" in message:
            print("请确认已在环境变量或 .env 中配置 BRAVE_API_KEY 或 BRAVE_SEARCH_API_KEY。")
        else:
            print("请检查当前网络、代理或防火墙设置，确认可以访问 Brave Search API。")
        return 1

    print_summary(payload, show_raw=args.raw)
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":
    main()
