"""@trace_step decorator — traces an intermediate step within an agent."""

from __future__ import annotations

from typing import Any, Callable, TypeVar, Union, overload

from agent_tracer_plus.core.models import SpanType
from agent_tracer_plus.decorators.base import create_span_wrapper, wrap_class

F = TypeVar("F", bound=Callable[..., Any])

@overload
def trace_step(func: F) -> F: ...
@overload
def trace_step(*, name: str = "", span_type: str | SpanType = "CHAIN", capture_input: bool = True, capture_output: bool = True) -> Callable[[F], F]: ...

def trace_step(
    func: F | None = None,
    *,
    name: str = "",
    span_type: str | SpanType = "CHAIN",
    capture_input: bool = True,
    capture_output: bool = True,
) -> Union[F, Callable[[F], F]]:
    """Decorator to trace an intermediate step (chain, retrieval, custom)."""
    def decorator(target: Any) -> Any:
        step_name = name or getattr(target, "__name__", str(target))
        st = SpanType(span_type) if isinstance(span_type, str) else span_type
        if isinstance(target, type):
            return wrap_class(target, span_type=st, name_prefix=step_name, capture_input=capture_input, capture_output=capture_output)
        return create_span_wrapper(target, span_name=step_name, span_type=st, capture_input=capture_input, capture_output=capture_output)

    if func is not None:
        return decorator(func)
    return decorator
