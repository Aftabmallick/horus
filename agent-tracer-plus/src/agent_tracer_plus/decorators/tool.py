"""@trace_tool decorator — traces tool/function invocations."""

from __future__ import annotations

from typing import Any, Callable, TypeVar, Union, overload

from agent_tracer_plus.core.models import SpanType
from agent_tracer_plus.decorators.base import create_span_wrapper, wrap_class

F = TypeVar("F", bound=Callable[..., Any])

@overload
def trace_tool(func: F) -> F: ...
@overload
def trace_tool(*, name: str = "", capture_input: bool = True, capture_output: bool = True) -> Callable[[F], F]: ...

def trace_tool(
    func: F | None = None,
    *,
    name: str = "",
    capture_input: bool = True,
    capture_output: bool = True,
) -> Union[F, Callable[[F], F]]:
    """Decorator to trace tool/function invocations."""
    def decorator(target: Any) -> Any:
        tool_name = name or getattr(target, "__name__", str(target))
        if isinstance(target, type):
            return wrap_class(target, span_type=SpanType.TOOL, name_prefix=tool_name, capture_input=capture_input, capture_output=capture_output)
        return create_span_wrapper(target, span_name=tool_name, span_type=SpanType.TOOL, capture_input=capture_input, capture_output=capture_output)
    if func is not None:
        return decorator(func)
    return decorator
