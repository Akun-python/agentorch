"""Static assets for the long-term memory graph experiment."""

from __future__ import annotations

from importlib.resources import files


def read_demo_browser_queries() -> str:
    return files(__package__).joinpath("demo_browser_queries.cypher").read_text(encoding="utf-8")


__all__ = ["read_demo_browser_queries"]
