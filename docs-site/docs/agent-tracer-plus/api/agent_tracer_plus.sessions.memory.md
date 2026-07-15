# Module: `agent_tracer_plus.sessions.memory`

Agent memory tracing — track what agents remember, forget, and retrieve.

## Class `MemoryOperation`
A single memory read/write operation.

## Class `AgentMemoryTracer`
Track agent memory operations across sessions.

Captures:
  - What entered short-term / long-term memory
  - What was retrieved vs what was forgotten
  - Memory utilization (context window usage)
  - Memory staleness (age of retrieved memories)

### `def __init__(self, max_context_tokens)`
### `def trace_write(self, key, content, memory_type, trace_id, span_id)`
Trace a memory write operation.

### `def trace_read(self, key, memory_type, trace_id, span_id)`
Trace a memory read operation.

### `def trace_delete(self, key, trace_id, span_id)`
Trace a memory delete (forget) operation.

### `def get_stats(self)`
Get memory operation statistics.

### `def get_operations(self, limit)`
Get recent memory operations.

## Function `trace_memory_op(operation, content, memory_type)`
Trace a memory read/write operation (simplified API).

