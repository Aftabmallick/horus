"""Async batch processor for buffered writes to storage backends.

Collects spans/traces in an in-memory queue and flushes them
to the storage backend in batches — reducing I/O overhead.
"""

from __future__ import annotations

import asyncio
import atexit
import threading
import time
from typing import TYPE_CHECKING, List, Optional

try:
    from prometheus_client import Gauge, Counter, Histogram
    HAS_PROMETHEUS = True
    
    # Define metrics at module level so they are registered once
    QUEUE_DEPTH = Gauge("batch_processor_queue_depth", "Current number of items in the batch queue")
    FLUSH_LATENCY = Histogram("batch_processor_flush_latency_seconds", "Time taken to flush a batch to storage")
    FLUSH_ERRORS = Counter("batch_processor_flush_errors_total", "Total number of failed batch flushes")
except ImportError:
    HAS_PROMETHEUS = False

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.utils.logger import get_logger

if TYPE_CHECKING:
    from agent_tracer_plus.storage.base import StorageBackend

logger = get_logger("processing.batch")

class CircuitBreaker:
    """Simple state-based circuit breaker to prevent cascading failures."""
    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - self.last_failure_time >= self.reset_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        # HALF_OPEN allows one test execution
        return True


class BatchProcessor:
    """Buffers trace/span data and flushes to storage in batches.

    Runs a background flush loop. Thread-safe.
    """

    def __init__(
        self,
        storage: StorageBackend,
        batch_size: int = 100,
        flush_interval: float = 5.0,
        max_queue_size: int = 10_000,
    ) -> None:
        self._storage = storage
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._max_queue_size = max_queue_size

        self._trace_queue: List[Trace] = []
        self._span_queue: List[Span] = []
        self._lock = threading.Lock()

        self._flush_task: Optional[asyncio.Task[None]] = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        self._circuit_breaker = CircuitBreaker()

        # Register shutdown handler
        atexit.register(self._sync_flush_on_exit)

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Start the background flush loop."""
        if self._running:
            return
        self._running = True
        self._loop = loop
        try:
            if loop and loop.is_running():
                self._flush_task = loop.create_task(self._flush_loop())
        except Exception:
            logger.debug("Could not start async flush loop, using sync mode")

    def enqueue_trace(self, trace: Trace) -> None:
        """Add a trace to the flush queue."""
        with self._lock:
            if len(self._trace_queue) >= self._max_queue_size:
                logger.warning("Trace queue full, dropping oldest trace")
                self._trace_queue.pop(0)
            self._trace_queue.append(trace)
            
            if HAS_PROMETHEUS:
                QUEUE_DEPTH.set(len(self._trace_queue) + len(self._span_queue))

        if self._should_flush():
            self._try_flush()

    def enqueue_span(self, span: Span) -> None:
        """Add a span to the flush queue."""
        with self._lock:
            if len(self._span_queue) >= self._max_queue_size:
                logger.warning("Span queue full, dropping oldest span")
                self._span_queue.pop(0)
            self._span_queue.append(span)

            if HAS_PROMETHEUS:
                QUEUE_DEPTH.set(len(self._trace_queue) + len(self._span_queue))

        if self._should_flush():
            self._try_flush()

    def _should_flush(self) -> bool:
        """Check if we should trigger a flush based on queue size."""
        return (len(self._trace_queue) + len(self._span_queue)) >= self._batch_size

    def _try_flush(self) -> None:
        """Try to trigger an async flush."""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.flush(), self._loop)

    async def flush(self) -> None:
        """Flush all queued data to storage."""
        if not self._circuit_breaker.can_execute():
            logger.warning("Circuit breaker OPEN. Skipping flush to prevent backend overload.")
            return

        traces_to_flush: List[Trace] = []
        spans_to_flush: List[Span] = []

        with self._lock:
            traces_to_flush = self._trace_queue.copy()
            spans_to_flush = self._span_queue.copy()
            self._trace_queue.clear()
            self._span_queue.clear()

        if not traces_to_flush and not spans_to_flush:
            return

        start_time = time.time()
        try:
            for trace in traces_to_flush:
                await self._storage.save_trace(trace)

            if spans_to_flush:
                await self._storage.save_spans_batch(spans_to_flush)
            
            self._circuit_breaker.record_success()
            
            if HAS_PROMETHEUS:
                FLUSH_LATENCY.observe(time.time() - start_time)
                
        except Exception as e:
            self._circuit_breaker.record_failure()
            if HAS_PROMETHEUS:
                FLUSH_ERRORS.inc()
            logger.error(f"Failed to flush batch: {e}")
            # Re-queue failed items (cap to avoid unbounded memory growth)
            with self._lock:
                # Merge and cap at max size
                new_traces = traces_to_flush + self._trace_queue
                self._trace_queue = new_traces[-self._max_queue_size:]
                
                new_spans = spans_to_flush + self._span_queue
                self._span_queue = new_spans[-self._max_queue_size:]
                
                if HAS_PROMETHEUS:
                    QUEUE_DEPTH.set(len(self._trace_queue) + len(self._span_queue))

    async def _flush_loop(self) -> None:
        """Background loop that periodically flushes the queue."""
        while self._running:
            try:
                await asyncio.sleep(self._flush_interval)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Flush loop error: {e}")

    def _sync_flush_on_exit(self) -> None:
        """Synchronous flush for atexit handler."""
        if not self._trace_queue and not self._span_queue:
            return
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self.flush())
            loop.close()
        except Exception as e:
            logger.error(f"Failed to flush on exit: {e}")

    async def shutdown(self) -> None:
        """Gracefully shut down the processor."""
        self._running = False
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self.flush()
        await self._storage.close()

    @property
    def pending_count(self) -> int:
        """Number of items waiting to be flushed."""
        return len(self._trace_queue) + len(self._span_queue)
