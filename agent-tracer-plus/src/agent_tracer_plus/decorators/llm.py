"""@trace_llm decorator — traces LLM calls with token/cost tracking."""

from __future__ import annotations

from typing import Any, Callable, Dict, TypeVar, Union, overload

from agent_tracer_plus.core.models import SpanType
from agent_tracer_plus.decorators.base import create_span_wrapper

F = TypeVar("F", bound=Callable[..., Any])

@overload
def trace_llm(func: F) -> F: ...
@overload
def trace_llm(*, name: str = "", model: str = "", track_tokens: bool = True, track_cost: bool = True, capture_input: bool = True, capture_output: bool = True) -> Callable[[F], F]: ...

def trace_llm(
    func: F | None = None,
    *,
    name: str = "",
    model: str = "",
    track_tokens: bool = True,
    track_cost: bool = True,
    capture_input: bool = True,
    capture_output: bool = True,
) -> Union[F, Callable[[F], F]]:
    """Decorator to trace LLM inference calls."""
    def decorator(target: Any) -> Any:
        llm_name = name or getattr(target, "__name__", str(target))
        attributes: Dict[str, Any] = {}
        if model:
            attributes["gen_ai.request.model"] = model
        attributes["gen_ai.track_tokens"] = track_tokens
        attributes["gen_ai.track_cost"] = track_cost
        return create_span_wrapper(
            target, span_name=llm_name, span_type=SpanType.LLM,
            attributes=attributes, capture_input=capture_input, capture_output=capture_output,
        )
    if func is not None:
        return decorator(func)
    return decorator
