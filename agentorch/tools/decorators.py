from __future__ import annotations

import inspect
from typing import Any, Callable, TypeVar, get_type_hints

from pydantic import BaseModel

from .base import FunctionTool

F = TypeVar("F", bound=Callable[..., Any])


def tool(
    *,
    name: str | None = None,
    description: str,
    risk_level: str = "low",
    timeout: float = 30.0,
    retryable: bool = False,
    needs_sandbox: bool = False,
) -> Callable[[F], FunctionTool]:
    def decorator(func: F) -> FunctionTool:
        hints = get_type_hints(func)
        parameters = list(inspect.signature(func).parameters.values())
        if len(parameters) != 1:
            raise TypeError("Tool functions must accept exactly one typed pydantic input parameter.")
        input_type = hints.get(parameters[0].name)
        if not input_type or not isinstance(input_type, type) or not issubclass(input_type, BaseModel):
            raise TypeError("Tool input parameter must be a pydantic BaseModel subclass.")
        return FunctionTool(
            name=name or func.__name__,
            description=description,
            input_model=input_type,
            func=func,
            risk_level=risk_level,
            timeout=timeout,
            retryable=retryable,
            needs_sandbox=needs_sandbox,
        )

    return decorator
