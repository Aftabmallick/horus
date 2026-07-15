"""@trace_handoff decorator — traces agent-to-agent handoffs."""

from __future__ import annotations

from typing import Any, Callable, Dict, TypeVar, Union, overload

from agent_tracer_plus.core.models import SpanType
from agent_tracer_plus.decorators.base import create_span_wrapper

F = TypeVar("F", bound=Callable[..., Any])

@overload
def trace_handoff(func: F) -> F: ...
@overload
def trace_handoff(*, source: str = "", target: str = "", name: str = "", capture_input: bool = True, capture_output: bool = True) -> Callable[[F], F]: ...

def trace_handoff(
    func: F | None = None,
    *,
    source: str = "",
    target: str = "",
    name: str = "",
    capture_input: bool = True,
    capture_output: bool = True,
) -> Union[F, Callable[[F], F]]:
    """Decorator to trace agent-to-agent handoffs."""
    def decorator(fn: Any) -> Any:
        handoff_name = name or f"handoff:{source}->{target}"
        attributes: Dict[str, Any] = {"handoff.source": source, "handoff.target": target}
        return create_span_wrapper(
            fn, span_name=handoff_name, span_type=SpanType.HANDOFF,
            attributes=attributes, capture_input=capture_input, capture_output=capture_output,
        )
    if func is not None:
        return decorator(func)
    return decorator
