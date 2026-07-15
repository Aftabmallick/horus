"""@trace_policy decorator — traces policy invocations."""

from __future__ import annotations

from typing import Any, Callable, TypeVar, Union, overload

from agent_tracer_plus.core.models import SpanType
from agent_tracer_plus.decorators.base import create_span_wrapper, wrap_class

F = TypeVar("F", bound=Callable[..., Any])

@overload
def trace_policy(func: F) -> F: ...
@overload
def trace_policy(*, name: str = "", capture_input: bool = True, capture_output: bool = True) -> Callable[[F], F]: ...

def trace_policy(
    func: F | None = None,
    *,
    name: str = "",
    capture_input: bool = True,
    capture_output: bool = True,
) -> Union[F, Callable[[F], F]]:
    """Decorator to trace policy invocations."""
    def decorator(target: Any) -> Any:
        span_name = name or getattr(target, "__name__", str(target))
        if isinstance(target, type):
            return wrap_class(target, span_type=SpanType.POLICY, name_prefix=span_name, capture_input=capture_input, capture_output=capture_output)
        return create_span_wrapper(target, span_name=span_name, span_type=SpanType.POLICY, capture_input=capture_input, capture_output=capture_output)
    if func is not None:
        return decorator(func)
    return decorator
