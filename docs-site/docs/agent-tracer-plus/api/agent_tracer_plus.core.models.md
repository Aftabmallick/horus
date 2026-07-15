# Module: `agent_tracer_plus.core.models`

Core data models for Agent Tracer Plus.

Defines the trace/span/event hierarchy used throughout the library.
All models are plain dataclasses — no external dependencies required.

## Class `SpanType`
Type of work a span represents.

## Class `SpanStatus`
Status of a span.

## Class `TraceStatus`
Status of a trace.

## Class `TokenUsage`
Token usage for an LLM call.

### `def __post_init__(self)`
## Class `CostInfo`
Cost information for an LLM call.

### `def __post_init__(self)`
## Class `SpanLink`
Link between spans across trace boundaries (for distributed tracing).

Used to connect agent-to-agent handoffs, where the child may
be in a different trace but causally related to this span.

## Class `Event`
A timestamped event within a span.

Events represent discrete moments (checkpoints, state changes,
guardrail triggers, etc.) rather than durations.

### `def to_dict(self)`
Serialize to a JSON-compatible dict.

## Class `Span`
A single unit of work within a trace.

Spans form a tree: each span has an optional parent_span_id.
The root span of a trace has parent_span_id = None.

### `def set_attribute(self, key, value)`
Set a custom attribute on this span.

### `def set_output(self, output)`
Set the output of this span.

### `def set_error(self, error)`
Record an error on this span.

### `def add_event(self, name, attributes)`
Add a timestamped event to this span.

### `def add_link(self, trace_id, span_id, link_type, attributes)`
Add a link to a span in another trace.

### `def finish(self, status)`
Mark this span as finished.

### `def to_dict(self)`
Serialize to a JSON-compatible dict.

### `def to_otlp(self)`
Serialize directly to OpenTelemetry Protobuf JSON mapping.

### `def from_dict(cls, data)`
Deserialize from a dict.

## Class `Trace`
Top-level container representing an end-to-end agent execution.

A trace contains one or more spans organized in a tree structure.
The execution_id groups multiple traces from a single logical operation.

### `def set_metadata(self, data)`
Merge metadata into the trace.

### `def add_tag(self, tag)`
Add a tag to the trace.

### `def add_span(self, span)`
Register a span with this trace.

### `def finish(self, status)`
Mark this trace as finished and compute aggregated metrics.

### `def to_dict(self)`
Serialize to a JSON-compatible dict.

### `def to_otlp(self)`
Serialize directly to OpenTelemetry Protobuf ResourceSpans mapping.

### `def from_dict(cls, data)`
Deserialize from a dict.

