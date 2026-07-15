"""In-memory storage backend for testing and development."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.base import StorageBackend


class InMemoryBackend(StorageBackend):
    """Stores traces and spans in memory. Data is lost on restart.

    Thread-safe via a lock. Ideal for unit tests and short-lived scripts.
    """

    def __init__(self, max_traces: int = 10_000) -> None:
        self._traces: Dict[str, Dict[str, Any]] = {}
        self._spans: Dict[str, List[Dict[str, Any]]] = {}  # trace_id -> [span_dicts]
        self._max_traces = max_traces
        self._lock = threading.Lock()

    async def save_trace(self, trace: Trace) -> None:
        with self._lock:
            # Evict oldest if at capacity
            if len(self._traces) >= self._max_traces:
                oldest_key = next(iter(self._traces))
                del self._traces[oldest_key]
                self._spans.pop(oldest_key, None)

            self._traces[trace.trace_id] = trace.to_dict()

    async def save_span(self, span: Span) -> None:
        with self._lock:
            if span.trace_id not in self._spans:
                self._spans[span.trace_id] = []
            self._spans[span.trace_id].append(span.to_dict())

    async def save_spans_batch(self, spans: List[Span]) -> None:
        with self._lock:
            for span in spans:
                if span.trace_id not in self._spans:
                    self._spans[span.trace_id] = []
                self._spans[span.trace_id].append(span.to_dict())

    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        with self._lock:
            data = self._traces.get(trace_id)
            if data is None:
                return None
            return Trace.from_dict(data)

    async def get_spans(self, trace_id: str) -> List[Span]:
        with self._lock:
            span_dicts = self._spans.get(trace_id, [])
            return [Span.from_dict(sd) for sd in span_dicts]

    async def query_traces(
        self,
        filters: Dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            traces = list(self._traces.values())

            if filters:
                for key, value in filters.items():
                    traces = [t for t in traces if t.get(key) == value]

            return traces[offset : offset + limit]

    async def delete_traces(self, before: datetime) -> int:
        with self._lock:
            to_delete = []
            for trace_id, data in self._traces.items():
                started = data.get("started_at", "")
                if started and started < before.isoformat():
                    to_delete.append(trace_id)

            for tid in to_delete:
                del self._traces[tid]
                self._spans.pop(tid, None)

            return len(to_delete)

    async def flush(self) -> None:
        pass  # No buffering in memory backend

    async def close(self) -> None:
        with self._lock:
            self._traces.clear()
            self._spans.clear()

    async def health_check(self) -> bool:
        return True

    # ── Convenience methods for testing ──

    @property
    def trace_count(self) -> int:
        """Number of stored traces."""
        return len(self._traces)

    @property
    def span_count(self) -> int:
        """Total number of stored spans across all traces."""
        return sum(len(spans) for spans in self._spans.values())

    def get_all_traces(self) -> List[Dict[str, Any]]:
        """Get all stored trace dicts."""
        return list(self._traces.values())

    def get_all_spans(self) -> List[Dict[str, Any]]:
        """Get all stored span dicts."""
        all_spans: List[Dict[str, Any]] = []
        for spans in self._spans.values():
            all_spans.extend(spans)
        return all_spans
