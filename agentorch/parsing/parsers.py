from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ValidationError


class ParseError(Exception):
    pass


class OutputParser:
    async def parse(self, payload: Any) -> Any:
        return payload


class PydanticParser(OutputParser):
    def __init__(self, model: type[BaseModel], auto_repair: bool = True) -> None:
        self.model = model
        self.auto_repair = auto_repair

    async def parse(self, payload: Any) -> BaseModel:
        try:
            return self.model.model_validate(payload)
        except ValidationError:
            if self.auto_repair:
                repaired = self._repair(payload)
                try:
                    return self.model.model_validate(repaired)
                except ValidationError as exc:
                    raise ParseError(str(exc)) from exc
            raise

    def _repair(self, payload: Any) -> Any:
        if isinstance(payload, str):
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return {"value": payload}
        return payload
