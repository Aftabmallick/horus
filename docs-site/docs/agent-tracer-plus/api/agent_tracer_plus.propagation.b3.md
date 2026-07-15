# Module: `agent_tracer_plus.propagation.b3`

B3 (Zipkin) trace context propagation.

Supports both single-header and multi-header B3 formats.
See: https://github.com/openzipkin/b3-propagation

## Class `B3TraceContextData`
Parsed B3 trace context.

### `def __init__(self, trace_id, span_id, sampled, parent_span_id)`
## Class `B3Propagator`
Injects/extracts B3 (Zipkin) trace context headers.

Supports:
  - Single header: b3: &#123;trace_id&#125;-&#123;span_id&#125;-&#123;sampling&#125;-&#123;parent_span_id&#125;
  - Multi-header: X-B3-TraceId, X-B3-SpanId, X-B3-Sampled, X-B3-ParentSpanId

### `def inject(self, carrier, single_header)`
Inject current trace context into carrier headers.

### `def extract(self, carrier)`
Extract B3 trace context from carrier headers.

### `def _parse_single(self, value)`
Parse B3 single-header format.

## Function `inject_b3(headers, single_header)`
Inject B3 trace context into headers.

## Function `extract_b3(headers)`
Extract B3 trace context from headers.

