# Module: `agent_tracer_plus`

Agent Tracer Plus — The Ultimate Agent Observability Platform.

## Function `init()`
Initialize Agent Tracer Plus globally.

Args:
    service_name: Name of your application/service.
    storage: Storage backend uri (e.g. "sqlite://./traces.db").
    **kwargs: Additional configuration options (see TracerConfig).

Returns:
    The initialized AgentTracerPlus instance.

## Function `current_trace()`
Get the currently active trace.

## Function `current_span()`
Get the currently active span.

