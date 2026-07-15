"""Base decorator logic shared by all trace decorators.

Handles the complexity of:
- Sync vs async function detection
- Class vs function decoration
- Method type detection (instance, static, classmethod)
- Generator / async generator support
- Error handling (never crashes the host app)
- functools.wraps preservation
"""

from __future__ import annotations

import asyncio
import functools
import inspect
from typing import Any, Callable, Dict, List, Set, TypeVar

from agent_tracer_plus.core.context import (
    SpanContext,
    TraceContext,
)
from agent_tracer_plus.core.models import SpanType
from agent_tracer_plus.utils.logger import get_logger
from agent_tracer_plus.utils.serialization import safe_serialize

logger = get_logger("decorators")

F = TypeVar("F", bound=Callable[..., Any])

# Dunder methods we never trace (except __call__ and __init__)
_SKIP_DUNDERS: Set[str] = {
    "__repr__", "__str__", "__hash__", "__eq__", "__ne__",
    "__lt__", "__le__", "__gt__", "__ge__", "__bool__",
    "__len__", "__getitem__", "__setitem__", "__delitem__",
    "__contains__", "__iter__", "__next__", "__del__",
    "__getattr__", "__setattr__", "__delattr__",
    "__get__", "__set__", "__delete__",
    "__new__", "__class_getitem__",
}


def _capture_args(func: Callable[..., Any], args: tuple, kwargs: dict, max_size: int = 10_000) -> Any:
    """Capture function arguments as a serializable dict."""
    try:
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        # Filter out 'self' and 'cls'
        params = {
            k: v for k, v in bound.arguments.items()
            if k not in ("self", "cls")
        }
        return safe_serialize(params, max_str_len=max_size)
    except Exception:
        # Fallback: just capture positional and keyword args
        try:
            filtered_args = args[1:] if args and hasattr(args[0], '__class__') else args
            return safe_serialize({"args": filtered_args, "kwargs": kwargs}, max_str_len=max_size)
        except Exception:
            return "<capture_failed>"


def create_span_wrapper(
    func: F,
    span_name: str,
    span_type: SpanType,
    attributes: Dict[str, Any] | None = None,
    capture_input: bool = True,
    capture_output: bool = True,
    is_root: bool = False,
) -> F:
    """Wrap a function (sync or async) with span creation and lifecycle management.

    This is the core wrapping logic used by all decorators.
    """
    is_async = asyncio.iscoroutinefunction(func)
    is_async_gen = inspect.isasyncgenfunction(func)
    is_gen = inspect.isgeneratorfunction(func)

    if is_async_gen:
        @functools.wraps(func)
        async def async_gen_wrapper(*args: Any, **kwargs: Any) -> Any:
            with SpanContext(name=span_name, span_type=span_type, attributes=attributes or {}) as span:
                if capture_input:
                    span.input = _capture_args(func, args, kwargs)
                try:
                    collected = []
                    async for item in func(*args, **kwargs):
                        collected.append(item)
                        yield item
                    if capture_output:
                        span.set_output(f"<async_generator: {len(collected)} items>")
                except Exception as e:
                    span.set_error(e)
                    raise
        return async_gen_wrapper  # type: ignore[return-value]

    if is_gen:
        @functools.wraps(func)
        def gen_wrapper(*args: Any, **kwargs: Any) -> Any:
            with SpanContext(name=span_name, span_type=span_type, attributes=attributes or {}) as span:
                if capture_input:
                    span.input = _capture_args(func, args, kwargs)
                try:
                    collected = []
                    for item in func(*args, **kwargs):
                        collected.append(item)
                        yield item
                    if capture_output:
                        span.set_output(f"<generator: {len(collected)} items>")
                except Exception as e:
                    span.set_error(e)
                    raise
        return gen_wrapper  # type: ignore[return-value]

    if is_async:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            if is_root:
                return await _run_as_root_async(func, args, kwargs, span_name, span_type, attributes, capture_input, capture_output)

            with SpanContext(name=span_name, span_type=span_type, attributes=attributes or {}) as span:
                if capture_input:
                    span.input = _capture_args(func, args, kwargs)

                from agent_tracer_plus.core.context import get_tracer
                tracer = get_tracer()
                if tracer:
                    should_mock, mock_out = tracer.check_replay(span_type.value, span_name, span.input)
                    if should_mock:
                        if capture_output:
                            span.set_output(safe_serialize(mock_out))
                        return mock_out

                try:
                    result = await func(*args, **kwargs)
                    if capture_output:
                        span.set_output(safe_serialize(result))
                    return result
                except Exception as e:
                    span.set_error(e)
                    raise
        return async_wrapper  # type: ignore[return-value]

    # Sync function
    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        if is_root:
            return _run_as_root_sync(func, args, kwargs, span_name, span_type, attributes, capture_input, capture_output)

        with SpanContext(name=span_name, span_type=span_type, attributes=attributes or {}) as span:
            if capture_input:
                span.input = _capture_args(func, args, kwargs)

            from agent_tracer_plus.core.context import get_tracer
            tracer = get_tracer()
            if tracer:
                should_mock, mock_out = tracer.check_replay(span_type.value, span_name, span.input)
                if should_mock:
                    if capture_output:
                        span.set_output(safe_serialize(mock_out))
                    return mock_out

            try:
                result = func(*args, **kwargs)
                if capture_output:
                    span.set_output(safe_serialize(result))
                return result
            except Exception as e:
                span.set_error(e)
                raise
    return sync_wrapper  # type: ignore[return-value]


async def _run_as_root_async(
    func: Callable, args: tuple, kwargs: dict,
    span_name: str, span_type: SpanType,
    attributes: Dict[str, Any] | None,
    capture_input: bool, capture_output: bool,
) -> Any:
    """Run a function as the root of a new trace (async version)."""
    with TraceContext(agent_name=span_name) as trace:
        with SpanContext(name=span_name, span_type=span_type, attributes=attributes or {}) as span:
            if capture_input:
                span.input = _capture_args(func, args, kwargs)
            try:
                result = await func(*args, **kwargs)
                if capture_output:
                    span.set_output(safe_serialize(result))
                return result
            except Exception as e:
                span.set_error(e)
                raise


def _run_as_root_sync(
    func: Callable, args: tuple, kwargs: dict,
    span_name: str, span_type: SpanType,
    attributes: Dict[str, Any] | None,
    capture_input: bool, capture_output: bool,
) -> Any:
    """Run a function as the root of a new trace (sync version)."""
    with TraceContext(agent_name=span_name) as trace:
        with SpanContext(name=span_name, span_type=span_type, attributes=attributes or {}) as span:
            if capture_input:
                span.input = _capture_args(func, args, kwargs)
            try:
                result = func(*args, **kwargs)
                if capture_output:
                    span.set_output(safe_serialize(result))
                return result
            except Exception as e:
                span.set_error(e)
                raise


def wrap_class(
    cls: type,
    span_type: SpanType,
    name_prefix: str,
    trace_methods: str = "public",
    exclude_methods: List[str] | None = None,
    include_private: bool = False,
    trace_init: bool = True,
    trace_dunder: bool = False,
    capture_input: bool = True,
    capture_output: bool = True,
    is_root: bool = False,
) -> type:
    """Wrap all eligible methods of a class with span creation.

    Args:
        cls: The class to wrap.
        span_type: Default span type for methods.
        name_prefix: Prefix for span names (usually the class name).
        trace_methods: "all" | "public" | "explicit_only"
        exclude_methods: Method names to skip.
        include_private: Whether to trace _private methods.
        trace_init: Whether to trace __init__.
        trace_dunder: Whether to trace dunder methods (except __call__/__init__).
        capture_input: Whether to capture method arguments.
        capture_output: Whether to capture return values.
        is_root: Whether the first call should create a new trace.
    """
    if trace_methods == "explicit_only":
        return cls

    exclude = set(exclude_methods or [])

    all_method_names = set()
    for base in cls.__mro__:
        if base is object:
            continue
        all_method_names.update(vars(base).keys())

    for attr_name in all_method_names:
        # Skip exclusions
        if attr_name in exclude:
            continue

        # Get the actual function, resolving through MRO
        attr = None
        for base in cls.__mro__:
            if attr_name in vars(base):
                attr = vars(base)[attr_name]
                break
        if attr is None:
            continue

        # Already decorated — explicit takes priority
        if hasattr(attr, "_atp_traced"):
            continue

        # Skip non-callables
        raw_attr = attr
        is_static = isinstance(raw_attr, staticmethod)
        is_classm = isinstance(raw_attr, classmethod)

        if is_static or is_classm:
            func = raw_attr.__func__
        elif callable(raw_attr):
            func = raw_attr
        else:
            continue

        # Skip non-functions (properties, descriptors, etc.)
        if not (inspect.isfunction(func) or inspect.ismethod(func)):
            continue

        # Dunder filtering
        if attr_name.startswith("__") and attr_name.endswith("__"):
            if attr_name == "__call__":
                pass  # Always trace __call__
            elif attr_name == "__init__" and trace_init:
                pass  # Trace __init__ if configured
            elif not trace_dunder:
                continue
            if attr_name in _SKIP_DUNDERS:
                continue

        # Private method filtering
        if attr_name.startswith("_") and not attr_name.startswith("__"):
            if not include_private:
                continue

        # Public method filtering
        if trace_methods == "public" and attr_name.startswith("_") and attr_name != "__init__" and attr_name != "__call__":
            if not include_private:
                continue

        # Determine if this is the root method (first call creates trace)
        method_is_root = is_root and attr_name in ("run", "__call__", "execute", "invoke", "__init__")

        # Wrap the function
        span_name = f"{name_prefix}.{attr_name}"
        wrapped = create_span_wrapper(
            func,
            span_name=span_name,
            span_type=span_type,
            capture_input=capture_input,
            capture_output=capture_output,
            is_root=method_is_root,
        )
        wrapped._atp_traced = True  # type: ignore[attr-defined]

        # Re-apply staticmethod/classmethod descriptors
        if is_static:
            setattr(cls, attr_name, staticmethod(wrapped))
        elif is_classm:
            setattr(cls, attr_name, classmethod(wrapped))
        else:
            setattr(cls, attr_name, wrapped)

    # Mark the class as traced
    cls._atp_traced = True  # type: ignore[attr-defined]
    return cls
