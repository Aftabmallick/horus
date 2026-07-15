"""Guardrail Monitoring Decorator for Agent Tracer Plus."""

import functools
from typing import Any, Callable, Optional

from agent_tracer_plus.core.context import SpanContext


class GuardrailResult:
    """Standard return type for guardrail functions."""
    def __init__(self, passed: bool, reason: str = "", metadata: dict = None):
        self.passed = passed
        self.reason = reason
        self.metadata = metadata or {}

    def __bool__(self):
        return self.passed

def trace_guardrail(name: Optional[str] = None, policy: str = "custom") -> Callable:
    """Decorator to trace guardrail validation layers.
    
    If the function returns a GuardrailResult or a bool, it will automatically
    log if the guardrail passed or failed.
    """
    def decorator(func: Callable) -> Callable:
        span_name = name or func.__name__

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            with SpanContext(span_name, span_type="GUARDRAIL") as span:
                span.set_attribute("guardrail.policy", policy)

                try:
                    result = func(*args, **kwargs)

                    if isinstance(result, GuardrailResult):
                        span.set_attribute("guardrail.passed", result.passed)
                        span.set_attribute("guardrail.reason", result.reason)
                        if not result.passed:
                            span.add_event("guardrail_block", {"reason": result.reason, **result.metadata})
                    elif isinstance(result, bool):
                        span.set_attribute("guardrail.passed", result)

                    return result
                except Exception as e:
                    span.record_exception(e)
                    raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            with SpanContext(span_name, span_type="GUARDRAIL") as span:
                span.set_attribute("guardrail.policy", policy)

                try:
                    result = await func(*args, **kwargs)

                    if isinstance(result, GuardrailResult):
                        span.set_attribute("guardrail.passed", result.passed)
                        span.set_attribute("guardrail.reason", result.reason)
                        if not result.passed:
                            span.add_event("guardrail_block", {"reason": result.reason, **result.metadata})
                    elif isinstance(result, bool):
                        span.set_attribute("guardrail.passed", result)

                    return result
                except Exception as e:
                    span.record_exception(e)
                    raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
