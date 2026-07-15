"""@trace_guardrail decorator — traces guardrail checks."""

from __future__ import annotations

from typing import Any, Callable, TypeVar, Union, overload

from agent_tracer_plus.core.models import SpanType
from agent_tracer_plus.decorators.base import create_span_wrapper

F = TypeVar("F", bound=Callable[..., Any])

@overload
def trace_guardrail(func: F) -> F: ...
@overload
def trace_guardrail(*, name: str = "", capture_input: bool = True, capture_output: bool = True) -> Callable[[F], F]: ...

def trace_guardrail(
    func: F | None = None,
    *,
    name: str = "",
    capture_input: bool = True,
    capture_output: bool = True,
) -> Union[F, Callable[[F], F]]:
    """Decorator to trace guardrail checks."""
    def decorator(fn: Any) -> Any:
        guard_name = name or getattr(fn, "__name__", str(fn))
        return create_span_wrapper(
            fn, span_name=guard_name, span_type=SpanType.GUARDRAIL,
            capture_input=capture_input, capture_output=capture_output,
        )
    if func is not None:
        return decorator(func)
    return decorator
