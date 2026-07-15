# Module: `agent_tracer_plus.core.context`

Context propagation using Python's contextvars.

This module manages the trace context across sync/async execution,
ensuring parent-child span relationships are maintained automatically.
Thread-safe and async-safe via contextvars.

## Function `get_current_trace()`
Get the current active trace, or None if no trace is active.

## Function `get_current_span()`
Get the current active span, or None if no span is active.

## Function `get_tracer()`
Get the global tracer instance.

## Function `set_tracer(tracer)`
Set the global tracer instance.

## Class `TraceContext`
Context manager that creates and manages a trace lifecycle.

Usage:
    with TraceContext(name="MyAgent") as trace:
        # trace is active here
        pass
    # trace is finished and flushed here

### `def __init__(self, agent_name, metadata, tags)`
### `def __enter__(self)`
### `def __exit__(self, exc_type, exc_val, exc_tb)`
## Class `SpanContext`
Context manager that creates and manages a span lifecycle.

Automatically links to the current trace and parent span.

Usage:
    with SpanContext(name="my_step", span_type=SpanType.TOOL) as span:
        span.set_attribute("key", "value")
        result = do_work()
        span.set_output(result)

### `def __init__(self, name, span_type, attributes)`
### `def __enter__(self)`
### `def __exit__(self, exc_type, exc_val, exc_tb)`
## Function `propagate_context(fn)`
Decorator that captures the current context and runs fn inside it.

Use this when submitting work to a ThreadPoolExecutor or threading.Thread
to ensure trace context is propagated to the worker thread.

Example:
    with ThreadPoolExecutor() as pool:
        future = pool.submit(propagate_context(my_function), arg1, arg2)

