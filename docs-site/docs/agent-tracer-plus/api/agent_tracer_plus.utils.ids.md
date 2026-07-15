# Module: `agent_tracer_plus.utils.ids`

ID generation utilities.

Generates globally unique, sortable identifiers for traces, spans, and executions.
Uses time-ordered UUIDs (UUID7-like) for sortability with UUID4 fallback guarantee.

## Function `_uuid7_like()`
Generate a time-ordered UUID similar to UUIDv7.

Format: 8-char timestamp hex + 24-char random hex = 32 hex chars.
This gives us chronological sortability while maintaining uniqueness.

## Function `generate_trace_id()`
Generate a unique trace ID (32 hex characters, W3C compatible).

Returns a 32-character hex string that is:
- Time-ordered for sortability
- Compatible with W3C Trace Context (128-bit trace-id)
- Globally unique across distributed systems

## Function `generate_span_id()`
Generate a unique span ID (16 hex characters, W3C compatible).

Returns a 16-character hex string compatible with W3C Trace Context (64-bit span-id).

## Function `generate_execution_id()`
Generate a unique execution ID.

This is a human-friendly ID used to correlate all traces
from a single logical execution (e.g., one API request).
Uses UUID4 for maximum uniqueness without time dependency.

