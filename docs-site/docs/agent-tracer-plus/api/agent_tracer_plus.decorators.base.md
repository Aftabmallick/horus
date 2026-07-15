# Module: `agent_tracer_plus.decorators.base`

Base decorator logic shared by all trace decorators.

Handles the complexity of:
- Sync vs async function detection
- Class vs function decoration
- Method type detection (instance, static, classmethod)
- Generator / async generator support
- Error handling (never crashes the host app)
- functools.wraps preservation

## Function `_capture_args(func, args, kwargs, max_size)`
Capture function arguments as a serializable dict.

## Function `create_span_wrapper(func, span_name, span_type, attributes, capture_input, capture_output, is_root)`
Wrap a function (sync or async) with span creation and lifecycle management.

This is the core wrapping logic used by all decorators.

## Function `_run_as_root_sync(func, args, kwargs, span_name, span_type, attributes, capture_input, capture_output)`
Run a function as the root of a new trace (sync version).

## Function `wrap_class(cls, span_type, name_prefix, trace_methods, exclude_methods, include_private, trace_init, trace_dunder, capture_input, capture_output, is_root)`
Wrap all eligible methods of a class with span creation.

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

