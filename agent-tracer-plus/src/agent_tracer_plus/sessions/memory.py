"""Agent memory tracing — track what agents remember, forget, and retrieve."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_tracer_plus.utils.clock import now_utc
from agent_tracer_plus.utils.ids import generate_span_id

logger = logging.getLogger(__name__)


@dataclass
class MemoryOperation:
    """A single memory read/write operation."""

    op_id: str = field(default_factory=generate_span_id)
    operation: str = ""  # "write", "read", "delete", "update"
    memory_type: str = "short_term"  # "short_term", "long_term", "episodic", "semantic"
    key: str = ""
    content_preview: str = ""  # Truncated content for tracing
    content_size_bytes: int = 0
    timestamp: datetime = field(default_factory=now_utc)
    hit: bool = True  # For reads: was the memory found?
    staleness_seconds: Optional[float] = None  # How old was the retrieved memory?
    trace_id: str = ""
    span_id: str = ""


class AgentMemoryTracer:
    """Track agent memory operations across sessions.

    Captures:
      - What entered short-term / long-term memory
      - What was retrieved vs what was forgotten
      - Memory utilization (context window usage)
      - Memory staleness (age of retrieved memories)
    """

    def __init__(self, max_context_tokens: int = 128_000) -> None:
        self.max_context_tokens = max_context_tokens
        self._operations: List[MemoryOperation] = []
        self._memory_state: Dict[str, Dict[str, Any]] = {}  # key -> {content, written_at, type}

    def trace_write(
        self,
        key: str,
        content: str,
        memory_type: str = "short_term",
        trace_id: str = "",
        span_id: str = "",
    ) -> MemoryOperation:
        """Trace a memory write operation."""
        op = MemoryOperation(
            operation="write",
            memory_type=memory_type,
            key=key,
            content_preview=content[:200],
            content_size_bytes=len(content.encode("utf-8")),
            trace_id=trace_id,
            span_id=span_id,
        )
        self._operations.append(op)
        self._memory_state[key] = {
            "content": content,
            "written_at": op.timestamp,
            "type": memory_type,
        }
        logger.debug(f"Memory WRITE: {key} ({memory_type}, {op.content_size_bytes}B)")
        return op

    def trace_read(
        self,
        key: str,
        memory_type: str = "short_term",
        trace_id: str = "",
        span_id: str = "",
    ) -> MemoryOperation:
        """Trace a memory read operation."""
        hit = key in self._memory_state
        staleness = None
        content_preview = ""

        if hit:
            entry = self._memory_state[key]
            staleness = (now_utc() - entry["written_at"]).total_seconds()
            content_preview = entry["content"][:200]

        op = MemoryOperation(
            operation="read",
            memory_type=memory_type,
            key=key,
            content_preview=content_preview,
            hit=hit,
            staleness_seconds=staleness,
            trace_id=trace_id,
            span_id=span_id,
        )
        self._operations.append(op)
        status = "HIT" if hit else "MISS"
        logger.debug(f"Memory READ: {key} ({status}, staleness={staleness}s)")
        return op

    def trace_delete(
        self,
        key: str,
        trace_id: str = "",
        span_id: str = "",
    ) -> MemoryOperation:
        """Trace a memory delete (forget) operation."""
        op = MemoryOperation(
            operation="delete",
            key=key,
            hit=key in self._memory_state,
            trace_id=trace_id,
            span_id=span_id,
        )
        self._operations.append(op)
        self._memory_state.pop(key, None)
        logger.debug(f"Memory DELETE: {key}")
        return op

    def get_stats(self) -> Dict[str, Any]:
        """Get memory operation statistics."""
        total = len(self._operations)
        writes = sum(1 for o in self._operations if o.operation == "write")
        reads = sum(1 for o in self._operations if o.operation == "read")
        deletes = sum(1 for o in self._operations if o.operation == "delete")
        hits = sum(1 for o in self._operations if o.operation == "read" and o.hit)
        misses = sum(1 for o in self._operations if o.operation == "read" and not o.hit)
        hit_rate = hits / reads * 100 if reads > 0 else 0

        # Staleness stats
        staleness_values = [o.staleness_seconds for o in self._operations if o.staleness_seconds is not None]
        avg_staleness = sum(staleness_values) / len(staleness_values) if staleness_values else 0

        # Memory utilization
        total_bytes = sum(len(v["content"].encode("utf-8")) for v in self._memory_state.values())
        
        # Memory Drift and Context Pollution Analysis
        drift_warnings = []
        if avg_staleness > 3600:
            drift_warnings.append("High staleness: Agent is heavily relying on memories older than 1 hour. Risk of context drift.")
            
        if total_bytes > self.max_context_tokens * 2: # Rough bytes-to-tokens conversion heuristic
            drift_warnings.append(f"Context pollution: Active memories ({total_bytes} bytes) exceed max context capacity. Agent will suffer severe amnesia or truncation.")
            
        if hit_rate < 20 and reads > 5:
            drift_warnings.append("Memory thrashing: Agent is repeatedly attempting to read forgotten or non-existent memories.")

        return {
            "total_operations": total,
            "writes": writes,
            "reads": reads,
            "deletes": deletes,
            "cache_hits": hits,
            "cache_misses": misses,
            "hit_rate_pct": round(hit_rate, 1),
            "avg_staleness_seconds": round(avg_staleness, 2),
            "active_memories": len(self._memory_state),
            "total_memory_bytes": total_bytes,
            "memory_types": {
                mt: sum(1 for v in self._memory_state.values() if v["type"] == mt)
                for mt in set(v["type"] for v in self._memory_state.values())
            },
            "drift_warnings": drift_warnings,
        }

    def get_operations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent memory operations."""
        ops = self._operations[-limit:]
        return [
            {
                "op_id": o.op_id,
                "operation": o.operation,
                "memory_type": o.memory_type,
                "key": o.key,
                "hit": o.hit,
                "staleness_seconds": o.staleness_seconds,
                "content_size_bytes": o.content_size_bytes,
                "timestamp": o.timestamp.isoformat(),
            }
            for o in ops
        ]


# Convenience function (backward compat with old stub)
def trace_memory_op(operation: str, content: str, memory_type: str = "short_term") -> None:
    """Trace a memory read/write operation (simplified API)."""
    from agent_tracer_plus import current_trace
    trace = current_trace()
    if trace:
        from agent_tracer_plus.core.context import SpanContext, SpanType
        with SpanContext(f"memory.{operation}", span_type=SpanType.CUSTOM, attributes={
            "memory.type": memory_type,
            "memory.operation": operation,
            "memory.content_preview": content[:200],
        }):
            logger.debug(f"Traced memory {operation} in {memory_type}")
