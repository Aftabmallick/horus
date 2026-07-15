"""Context propagation using Python's contextvars.

This module manages the trace context across sync/async execution,
ensuring parent-child span relationships are maintained automatically.
Thread-safe and async-safe via contextvars.
"""

from __future__ import annotations

import contextvars
import functools
from typing import TYPE_CHECKING, Any, Callable, Optional, TypeVar

from agent_tracer_plus.core.models import Span, SpanStatus, SpanType, Trace
from agent_tracer_plus.utils.clock import monotonic_ns, now_utc
from agent_tracer_plus.utils.ids import generate_span_id
from agent_tracer_plus.utils.logger import get_logger

if TYPE_CHECKING:
    from agent_tracer_plus.core.tracer import AgentTracerPlus

logger = get_logger("context")

F = TypeVar("F", bound=Callable[..., Any])

# ── Context Variables ──────────────────────────────────────────────────────────

# The current active trace for this execution context
_current_trace: contextvars.ContextVar[Optional[Trace]] = contextvars.ContextVar(
    "atp_current_trace", default=None
)

# The current active span (most recently entered)
_current_span: contextvars.ContextVar[Optional[Span]] = contextvars.ContextVar(
    "atp_current_span", default=None
)

# Reference to the global tracer instance
_tracer_instance: contextvars.ContextVar[Optional[AgentTracerPlus]] = contextvars.ContextVar(
    "atp_tracer_instance", default=None
)


# ── Public API ─────────────────────────────────────────────────────────────────


def get_current_trace() -> Optional[Trace]:
    """Get the current active trace, or None if no trace is active."""
    return _current_trace.get()


def get_current_span() -> Optional[Span]:
    """Get the current active span, or None if no span is active."""
    return _current_span.get()


def get_tracer() -> Optional[AgentTracerPlus]:
    """Get the global tracer instance."""
    import agent_tracer_plus
    return agent_tracer_plus._tracer


def set_tracer(tracer: AgentTracerPlus) -> None:
    """Set the global tracer instance."""
    _tracer_instance.set(tracer)


# ── Trace Context Manager ─────────────────────────────────────────────────────


class TraceContext:
    """Context manager that creates and manages a trace lifecycle.

    Usage:
        with TraceContext(name="MyAgent") as trace:
            # trace is active here
            pass
        # trace is finished and flushed here
    """

    def __init__(
        self,
        agent_name: str = "",
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> None:
        self._agent_name = agent_name
        self._metadata = metadata or {}
        self._tags = tags or []
        self._token: contextvars.Token[Optional[Trace]] | None = None
        self._trace: Optional[Trace] = None

    def __enter__(self) -> Trace:
        tracer = get_tracer()
        self._trace = Trace(
            agent_name=self._agent_name,
            service_name=tracer.config.service_name if tracer else "",
            metadata=self._metadata,
            tags=self._tags,
            _start_monotonic_ns=monotonic_ns(),
        )
        if tracer:
            self._trace.tenant_id = tracer.config.tenant_id

        # Auto-inject active session context
        try:
            from agent_tracer_plus.sessions.tracker import inject_session_into_trace
            inject_session_into_trace(self._trace)
        except Exception:
            pass

        self._token = _current_trace.set(self._trace)
        return self._trace

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._trace is not None:
            if exc_val is not None:
                self._trace.finish(status="ERROR")
            else:
                self._trace.finish()

            # Flush to storage
            tracer = get_tracer()
            if tracer:
                tracer._enqueue_trace(self._trace)

        if self._token is not None:
            _current_trace.reset(self._token)

        return None  # Don't suppress exceptions


# ── Span Context Manager ──────────────────────────────────────────────────────


class SpanContext:
    """Context manager that creates and manages a span lifecycle.

    Automatically links to the current trace and parent span.

    Usage:
        with SpanContext(name="my_step", span_type=SpanType.TOOL) as span:
            span.set_attribute("key", "value")
            result = do_work()
            span.set_output(result)
    """

    def __init__(
        self,
        name: str,
        span_type: SpanType = SpanType.CUSTOM,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        self._name = name
        self._span_type = span_type
        self._attributes = attributes or {}
        self._span: Optional[Span] = None
        self._span_token: contextvars.Token[Optional[Span]] | None = None

    def __enter__(self) -> Span:
        trace = get_current_trace()
        parent_span = get_current_span()

        self._span = Span(
            name=self._name,
            span_type=self._span_type,
            span_id=generate_span_id(),
            trace_id=trace.trace_id if trace else "",
            parent_span_id=parent_span.span_id if parent_span else None,
            started_at=now_utc(),
            _start_monotonic_ns=monotonic_ns(),
            attributes=self._attributes.copy(),
        )

        # Register with trace
        if trace:
            trace.add_span(self._span)

        # Trigger plugins
        tracer = get_tracer()
        if tracer and hasattr(tracer, "plugin_loader"):
            tracer.plugin_loader.trigger_on_span_start(self._span)

        # Chaos fault injection (before execution)
        if tracer and hasattr(tracer, "chaos_monkey") and tracer.chaos_monkey:
            tracer.chaos_monkey.inject_sync(self._name)

        # Set as current span
        self._span_token = _current_span.set(self._span)

        return self._span

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._span is not None:
            if exc_val is not None:
                self._span.set_error(exc_val)
                self._span.finish(status=SpanStatus.ERROR)
            else:
                self._span.finish()

            # Flush span to storage
            tracer = get_tracer()
            if tracer:
                tracer._enqueue_span(self._span)

                # Check budget (if trace is active)
                current_t = get_current_trace()
                if current_t and tracer.budget_enforcer:
                    tracer.budget_enforcer.check_budget(current_t)

        # Restore parent span
        if self._span_token is not None:
            _current_span.reset(self._span_token)

        return None


# ── Cross-Thread Propagation Helper ───────────────────────────────────────────


def propagate_context(fn: F) -> F:
    """Decorator that captures the current context and runs fn inside it.

    Use this when submitting work to a ThreadPoolExecutor or threading.Thread
    to ensure trace context is propagated to the worker thread.

    Example:
        with ThreadPoolExecutor() as pool:
            future = pool.submit(propagate_context(my_function), arg1, arg2)
    """
    ctx = contextvars.copy_context()

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return ctx.run(fn, *args, **kwargs)

    return wrapper  # type: ignore[return-value]
