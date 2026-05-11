from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from agentorch.parsing import OutputParser, ParseError, PydanticParser

T = TypeVar("T", bound=BaseModel)


class DramaPydanticRepairParser(OutputParser[T]):
    """修复多智能体角色前缀包裹的短剧 JSON 输出。"""

    format_name = "drama_pydantic_repair"

    def __init__(self, model: type[T]) -> None:
        self.model = model
        self._primary = PydanticParser(model)

    async def parse(self, payload: Any) -> T:
        errors: list[str] = []
        try:
            return await self._primary.parse(payload)  # type: ignore[return-value]
        except (ParseError, ValidationError) as exc:
            errors.append(str(exc))

        valid_items: list[tuple[int, int, T]] = []
        for index, candidate in enumerate(_iter_candidate_payloads(payload)):
            try:
                parsed = self.model.model_validate(candidate)
            except ValidationError as exc:
                errors.append(str(exc))
                continue
            valid_items.append((_richness_score(parsed.model_dump()), index, parsed))

        if valid_items:
            valid_items.sort(key=lambda item: (item[0], item[1]))
            return valid_items[-1][2]

        preview = _preview_payload(payload)
        detail = errors[-1] if errors else "未找到可校验的 JSON 对象"
        raise ParseError(f"{self.model.__name__} 解析失败：{detail}；原始输出预览：{preview}")

    def get_format_instructions(self) -> str:
        return (
            self._primary.get_format_instructions()
            + "\n最终回答只能输出一个 JSON 对象；不要带 [writer]/[director]/[reviewer] 前缀，不要输出 Markdown 代码块。"
        )


def _iter_candidate_payloads(payload: Any, *, max_depth: int = 4) -> list[Any]:
    candidates: list[Any] = []
    seen_text: set[str] = set()
    seen_objects: set[int] = set()

    def visit(value: Any, depth: int) -> None:
        if depth > max_depth:
            return
        if isinstance(value, (dict, list)):
            object_id = id(value)
            if object_id in seen_objects:
                return
            seen_objects.add(object_id)
            candidates.append(value)
            iterable = value.values() if isinstance(value, dict) else value
            for child in iterable:
                visit(child, depth + 1)
            return
        if not isinstance(value, str):
            return
        for text in _extract_json_text_candidates(value):
            if text in seen_text:
                continue
            seen_text.add(text)
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            candidates.append(parsed)
            visit(parsed, depth + 1)

    visit(payload, 0)
    return candidates


def _extract_json_text_candidates(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []

    candidates: list[str] = [stripped]
    without_role_prefix = re.sub(r"(?m)^\s*\[[^\]\n]{1,32}\]\s*", "", stripped).strip()
    if without_role_prefix and without_role_prefix != stripped:
        candidates.append(without_role_prefix)

    fence_pattern = re.compile(r"```(?:[a-zA-Z0-9_-]+)?\s*(.*?)```", re.DOTALL)
    for source in (stripped, without_role_prefix):
        for match in fence_pattern.finditer(source):
            fenced = match.group(1).strip()
            if fenced:
                candidates.append(fenced)
                candidates.extend(_extract_balanced_json_objects(fenced))

    candidates.extend(_extract_balanced_json_objects(stripped))
    if without_role_prefix != stripped:
        candidates.extend(_extract_balanced_json_objects(without_role_prefix))

    first = stripped.find("{")
    last = stripped.rfind("}")
    if first >= 0 and last > first:
        candidates.append(stripped[first : last + 1].strip())

    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        cleaned = candidate.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def _extract_balanced_json_objects(text: str) -> list[str]:
    candidates: list[str] = []
    depth = 0
    start_index: int | None = None
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start_index = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start_index is not None:
                candidates.append(text[start_index : index + 1].strip())
                start_index = None
    return candidates


def _richness_score(value: Any) -> int:
    if isinstance(value, BaseModel):
        return _richness_score(value.model_dump())
    if isinstance(value, dict):
        score = len([item for item in value.values() if item not in (None, "", [], {})])
        return score + sum(_richness_score(item) for item in value.values())
    if isinstance(value, list):
        return len(value) + sum(_richness_score(item) for item in value)
    if isinstance(value, str):
        return 1 if value.strip() else 0
    return 1 if value is not None else 0


def _preview_payload(payload: Any, *, limit: int = 260) -> str:
    text = payload if isinstance(payload, str) else repr(payload)
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit] + "..."
