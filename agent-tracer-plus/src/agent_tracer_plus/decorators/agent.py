"""@trace_agent decorator — marks the top-level agent execution."""

from __future__ import annotations

from typing import Any, Callable, List, TypeVar, Union, overload

from agent_tracer_plus.core.models import SpanType
from agent_tracer_plus.decorators.base import create_span_wrapper, wrap_class

F = TypeVar("F", bound=Callable[..., Any])


@overload
def trace_agent(func: F) -> F: ...
@overload
def trace_agent(
    *,
    name: str = "",
    tags: List[str] | None = None,
    trace_methods: str = "public",
    exclude_methods: List[str] | None = None,
    include_private: bool = False,
    trace_init: bool = True,
    trace_dunder: bool = False,
    capture_input: bool = True,
    capture_output: bool = True,
) -> Callable[[F], F]: ...


def trace_agent(
    func: F | None = None,
    *,
    name: str = "",
    tags: List[str] | None = None,
    trace_methods: str = "public",
    exclude_methods: List[str] | None = None,
    include_private: bool = False,
    trace_init: bool = True,
    trace_dunder: bool = False,
    capture_input: bool = True,
    capture_output: bool = True,
) -> Union[F, Callable[[F], F]]:
    """Decorator to trace an agent function or class.

    Creates a new Trace + root Span when the decorated function/method is called.

    Can be used as:
        @trace_agent
        def my_agent(): ...

        @trace_agent(name="MyAgent")
        class MyAgent: ...
    """
    def decorator(target: Any) -> Any:
        agent_name = name or getattr(target, "__name__", str(target))
        attributes = {"tags": tags or []}

        if isinstance(target, type):
            return wrap_class(
                target,
                span_type=SpanType.AGENT,
                name_prefix=agent_name,
                trace_methods=trace_methods,
                exclude_methods=exclude_methods,
                include_private=include_private,
                trace_init=trace_init,
                trace_dunder=trace_dunder,
                capture_input=capture_input,
                capture_output=capture_output,
                is_root=True,
            )

        return create_span_wrapper(
            target,
            span_name=agent_name,
            span_type=SpanType.AGENT,
            attributes=attributes,
            capture_input=capture_input,
            capture_output=capture_output,
            is_root=True,
        )

    if func is not None:
        return decorator(func)
    return decorator
