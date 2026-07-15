# Module: `agent_tracer_plus.propagation.w3c`

W3C Trace Context propagation (traceparent + tracestate headers).

Implements injection into outgoing requests and extraction from incoming requests.
See: https://www.w3.org/TR/trace-context/

## Class `TraceContextData`
Parsed W3C Trace Context.

### `def __init__(self, trace_id, span_id, trace_flags)`
## Class `W3CTraceContextPropagator`
Injects/extracts W3C traceparent headers.

### `def inject(self, carrier)`
### `def extract(self, carrier)`
## Function `inject_context(headers)`
Inject current trace context into headers dict.

## Function `extract_context(headers)`
Extract trace context from headers dict.

