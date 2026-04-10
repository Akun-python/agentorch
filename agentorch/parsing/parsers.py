from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T")


class ParseError(Exception):
    """Raised when a payload cannot be parsed into the requested structure."""


@dataclass(slots=True)
class ParsedRunResult(Generic[T]):
    """Convenience wrapper for parsed agent runs."""

    raw: Any
    parsed: T
    parser_name: str


class OutputParser(Generic[T]):
    """Base parser abstraction used to normalize model outputs."""

    format_name = "raw"

    async def parse(self, payload: Any) -> T:
        return payload

    def get_format_instructions(self) -> str:
        return "Return the answer as plain text."

    def with_prompt(self, prompt: str) -> str:
        return f"{prompt}\n\nOutput format:\n{self.get_format_instructions()}".strip()

    def parse_sync(self, payload: Any) -> T:
        try:
            import asyncio

            asyncio.get_running_loop()
        except RuntimeError:
            import asyncio as _asyncio

            return _asyncio.run(self.parse(payload))
        raise RuntimeError(
            "OutputParser.parse_sync() cannot be used inside a running event loop. "
            "Use 'await parser.parse(...)' in async applications."
        )


class TextParser(OutputParser[str]):
    format_name = "text"

    async def parse(self, payload: Any) -> str:
        if payload is None:
            return ""
        if isinstance(payload, str):
            return payload.strip()
        return str(payload).strip()

    def get_format_instructions(self) -> str:
        return "Return plain text only. Do not wrap the answer in JSON or Markdown code fences."


class JSONParser(OutputParser[Any]):
    format_name = "json"

    def __init__(self, *, strict: bool = False) -> None:
        self.strict = strict

    async def parse(self, payload: Any) -> Any:
        if isinstance(payload, (dict, list)):
            return payload
        if not isinstance(payload, str):
            raise ParseError(f"JSONParser expected str, dict, or list, got {type(payload).__name__}.")

        candidates = [payload]
        if not self.strict:
            extracted = _extract_json_candidates(payload)
            candidates.extend(item for item in extracted if item not in candidates)

        for candidate in candidates:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        raise ParseError("Unable to parse payload as JSON.")

    def get_format_instructions(self) -> str:
        return "Return valid JSON only. Do not add commentary, headings, or Markdown code fences."


class ListParser(OutputParser[list[str]]):
    format_name = "list"

    def __init__(self, *, drop_empty: bool = True) -> None:
        self.drop_empty = drop_empty
        self._json_parser = JSONParser()

    async def parse(self, payload: Any) -> list[str]:
        if isinstance(payload, list):
            return [str(item).strip() for item in payload if str(item).strip() or not self.drop_empty]

        if isinstance(payload, str):
            try:
                parsed = await self._json_parser.parse(payload)
            except ParseError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip() or not self.drop_empty]

            lines = []
            for line in payload.splitlines():
                cleaned = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s*", "", line).strip()
                if cleaned or not self.drop_empty:
                    lines.append(cleaned)
            if lines:
                return lines

        raise ParseError("Unable to parse payload as a list.")

    def get_format_instructions(self) -> str:
        return "Return a JSON array of strings."


class KeyValueParser(OutputParser[dict[str, Any]]):
    format_name = "key_value"

    def __init__(self) -> None:
        self._json_parser = JSONParser()

    async def parse(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload

        if isinstance(payload, str):
            try:
                parsed = await self._json_parser.parse(payload)
            except ParseError:
                parsed = None
            if isinstance(parsed, dict):
                return parsed

            result: dict[str, Any] = {}
            for line in payload.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                separator = ":" if ":" in stripped else "=" if "=" in stripped else None
                if separator is None:
                    continue
                key, value = stripped.split(separator, 1)
                result[key.strip()] = value.strip()
            if result:
                return result

        raise ParseError("Unable to parse payload as key-value data.")

    def get_format_instructions(self) -> str:
        return "Return a JSON object."


class PydanticParser(OutputParser[BaseModel]):
    format_name = "pydantic"

    def __init__(self, model: type[BaseModel], auto_repair: bool = True) -> None:
        self.model = model
        self.auto_repair = auto_repair
        self._json_parser = JSONParser()

    async def parse(self, payload: Any) -> BaseModel:
        try:
            return self.model.model_validate(payload)
        except ValidationError:
            if self.auto_repair:
                repaired = await self._repair(payload)
                try:
                    return self.model.model_validate(repaired)
                except ValidationError as exc:
                    raise ParseError(str(exc)) from exc
            raise

    def get_format_instructions(self) -> str:
        schema = self.model.model_json_schema()
        example = json.dumps(schema.get("properties", {}), ensure_ascii=False)
        return (
            "Return a valid JSON object matching this schema. "
            f"Required fields: {schema.get('required', [])}. "
            f"Properties: {example}. "
            "Do not add commentary or Markdown code fences."
        )

    async def _repair(self, payload: Any) -> Any:
        if isinstance(payload, str):
            try:
                return await self._json_parser.parse(payload)
            except ParseError:
                return {"value": payload.strip()}
        return payload


class FallbackParser(OutputParser[Any]):
    format_name = "fallback"

    def __init__(self, *parsers: OutputParser[Any]) -> None:
        if not parsers:
            raise ValueError("FallbackParser requires at least one parser.")
        self.parsers = parsers

    async def parse(self, payload: Any) -> Any:
        errors: list[str] = []
        for parser in self.parsers:
            try:
                return await parser.parse(payload)
            except (ParseError, ValidationError) as exc:
                errors.append(f"{parser.__class__.__name__}: {exc}")
        raise ParseError("; ".join(errors) or "All parsers failed.")

    def get_format_instructions(self) -> str:
        instructions = [parser.get_format_instructions() for parser in self.parsers]
        return "Prefer one of these formats:\n- " + "\n- ".join(instructions)


def parser_chain(*parsers: OutputParser[Any]) -> FallbackParser:
    return FallbackParser(*parsers)


def parse_json(payload: Any, *, strict: bool = False) -> Any:
    return JSONParser(strict=strict).parse_sync(payload)


def parse_list(payload: Any) -> list[str]:
    return ListParser().parse_sync(payload)


def parse_key_values(payload: Any) -> dict[str, Any]:
    return KeyValueParser().parse_sync(payload)


def parse_pydantic(payload: Any, model: type[BaseModel], *, auto_repair: bool = True) -> BaseModel:
    return PydanticParser(model, auto_repair=auto_repair).parse_sync(payload)


def format_prompt(prompt: str, parser: OutputParser[Any]) -> str:
    return parser.with_prompt(prompt)


def _extract_json_candidates(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []

    candidates: list[str] = []
    fence_pattern = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
    for match in fence_pattern.finditer(text):
        candidate = match.group(1).strip()
        if candidate:
            candidates.append(candidate)

    stack: list[str] = []
    start_index: int | None = None
    for index, char in enumerate(text):
        if char in "{[":
            if not stack:
                start_index = index
            stack.append("}" if char == "{" else "]")
        elif stack and char == stack[-1]:
            stack.pop()
            if not stack and start_index is not None:
                candidates.append(text[start_index : index + 1].strip())
                start_index = None
    return candidates
