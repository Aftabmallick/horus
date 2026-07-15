"""Prometheus metrics for Agent Tracer Plus self-monitoring.

Exposes internal SDK health metrics so the tracer itself is observable.
These are opt-in and require `prometheus_client` to be installed.

Metrics exposed:
    - agent_tracer_spans_processed_total (Counter): Total spans processed
    - agent_tracer_traces_processed_total (Counter): Total traces processed
    - agent_tracer_queue_depth (Gauge): Current batch processor queue depth
    - agent_tracer_flush_latency_seconds (Histogram): Time to flush a batch
    - agent_tracer_drop_total (Counter): Spans dropped due to queue overflow
    - agent_tracer_backend_errors_total (Counter): Storage backend write errors
    - agent_tracer_batch_size (Histogram): Size of each flushed batch

Usage::

    from agent_tracer_plus.processing.metrics import TracerMetrics
    metrics = TracerMetrics()
    metrics.record_span_processed()
    metrics.record_flush(batch_size=50, latency_seconds=0.012)
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Generator, Optional

logger = logging.getLogger("agent_tracer_plus.processing.metrics")

# Lazy import — prometheus_client is optional
_prometheus_available = False
_Counter = None
_Gauge = None
_Histogram = None


def _try_import_prometheus() -> bool:
    global _prometheus_available, _Counter, _Gauge, _Histogram
    if _prometheus_available:
        return True
    try:
        from prometheus_client import Counter, Gauge, Histogram
        _Counter = Counter
        _Gauge = Gauge
        _Histogram = Histogram
        _prometheus_available = True
        return True
    except ImportError:
        return False


class TracerMetrics:
    """Prometheus metrics registry for SDK self-monitoring.

    If `prometheus_client` is not installed, all methods are no-ops.
    """

    def __init__(self, namespace: str = "agent_tracer") -> None:
        self.namespace = namespace
        self._enabled = _try_import_prometheus()
        self._initialized = False
        self._metrics: dict = {}

        if self._enabled:
            self._init_metrics()

    def _init_metrics(self) -> None:
        """Initialize all Prometheus metric objects."""
        try:
            ns = self.namespace
            self._metrics["spans_processed"] = _Counter(
                f"{ns}_spans_processed_total",
                "Total number of spans processed by the batch processor",
                ["status"],  # status: success | error
            )
            self._metrics["traces_processed"] = _Counter(
                f"{ns}_traces_processed_total",
                "Total number of traces flushed to storage",
                ["status"],
            )
            self._metrics["queue_depth"] = _Gauge(
                f"{ns}_queue_depth",
                "Current number of items in the batch processor queue",
            )
            self._metrics["flush_latency"] = _Histogram(
                f"{ns}_flush_latency_seconds",
                "Time taken to flush a batch to the storage backend",
                buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            )
            self._metrics["drops"] = _Counter(
                f"{ns}_drop_total",
                "Total spans dropped due to queue overflow or unrecoverable error",
                ["reason"],
            )
            self._metrics["backend_errors"] = _Counter(
                f"{ns}_backend_errors_total",
                "Total storage backend write errors",
                ["backend"],
            )
            self._metrics["batch_size"] = _Histogram(
                f"{ns}_batch_size",
                "Number of spans in each flushed batch",
                buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000],
            )
            self._initialized = True
            logger.info(f"[TracerMetrics] Prometheus metrics initialized under namespace '{ns}'")
        except Exception as exc:
            # Don't crash the tracer if metrics fail to register (e.g. duplicate registration)
            logger.warning(f"[TracerMetrics] Failed to initialize metrics: {exc}")
            self._enabled = False

    def record_span_processed(self, status: str = "success") -> None:
        """Increment the spans processed counter."""
        if not self._enabled or not self._initialized:
            return
        try:
            self._metrics["spans_processed"].labels(status=status).inc()
        except Exception:
            pass

    def record_trace_flushed(self, status: str = "success") -> None:
        """Increment the traces flushed counter."""
        if not self._enabled or not self._initialized:
            return
        try:
            self._metrics["traces_processed"].labels(status=status).inc()
        except Exception:
            pass

    def set_queue_depth(self, depth: int) -> None:
        """Update the queue depth gauge."""
        if not self._enabled or not self._initialized:
            return
        try:
            self._metrics["queue_depth"].set(depth)
        except Exception:
            pass

    def record_flush(self, batch_size: int, latency_seconds: float) -> None:
        """Record a completed flush operation."""
        if not self._enabled or not self._initialized:
            return
        try:
            self._metrics["flush_latency"].observe(latency_seconds)
            self._metrics["batch_size"].observe(batch_size)
        except Exception:
            pass

    def record_drop(self, reason: str = "queue_overflow") -> None:
        """Increment the drop counter."""
        if not self._enabled or not self._initialized:
            return
        try:
            self._metrics["drops"].labels(reason=reason).inc()
        except Exception:
            pass

    def record_backend_error(self, backend_name: str = "unknown") -> None:
        """Increment the backend error counter."""
        if not self._enabled or not self._initialized:
            return
        try:
            self._metrics["backend_errors"].labels(backend=backend_name).inc()
        except Exception:
            pass

    @contextmanager
    def timed_flush(self) -> Generator[None, None, None]:
        """Context manager that measures and records flush latency."""
        start = time.monotonic()
        try:
            yield
        finally:
            elapsed = time.monotonic() - start
            if self._enabled and self._initialized:
                try:
                    self._metrics["flush_latency"].observe(elapsed)
                except Exception:
                    pass

    def is_available(self) -> bool:
        """Return True if prometheus_client is available and metrics are initialized."""
        return self._enabled and self._initialized


# Global singleton — zero-overhead if prometheus_client not installed
tracer_metrics = TracerMetrics()
