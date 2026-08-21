"""长期记忆图谱实验的静态资产入口。"""

from __future__ import annotations

from importlib.resources import files


def read_demo_browser_queries() -> str:
    """读取 Neo4j Browser 演示查询。"""

    return files(__package__).joinpath("demo_browser_queries.cypher").read_text(encoding="utf-8")


__all__ = ["read_demo_browser_queries"]
