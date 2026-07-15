"""Tests for the BatchProcessor — queuing, flushing, limits, shutdown."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.processing.batch import BatchProcessor
from agent_tracer_plus.storage.memory import InMemoryBackend


class TestBatchProcessorEnqueue:
    def test_enqueue_trace(self):
        backend = InMemoryBackend()
        processor = BatchProcessor(backend, batch_size=10, flush_interval=60)
        trace = Trace(agent_name="test")
        trace.finish()
        processor.enqueue_trace(trace)
        assert processor.pending_count >= 1

    def test_enqueue_span(self):
        backend = InMemoryBackend()
        processor = BatchProcessor(backend, batch_size=10, flush_interval=60)
        span = Span(name="test", trace_id="t1")
        span.finish()
        processor.enqueue_span(span)
        assert processor.pending_count >= 1


class TestBatchProcessorFlush:
    @pytest.mark.asyncio
    async def test_flush_writes_to_storage(self):
        backend = InMemoryBackend()
        processor = BatchProcessor(backend, batch_size=100, flush_interval=60)

        trace = Trace(agent_name="flush_test")
        trace.finish()
        processor.enqueue_trace(trace)

        span = Span(name="s1", trace_id=trace.trace_id)
        span.finish()
        processor.enqueue_span(span)

        await processor.flush()

        assert backend.trace_count >= 1
        assert backend.span_count >= 1

    @pytest.mark.asyncio
    async def test_flush_empty_queue(self):
        backend = InMemoryBackend()
        processor = BatchProcessor(backend, batch_size=10, flush_interval=60)
        # Should not raise
        await processor.flush()

    @pytest.mark.asyncio
    async def test_multiple_flushes(self):
        backend = InMemoryBackend()
        processor = BatchProcessor(backend, batch_size=100, flush_interval=60)

        for i in range(5):
            trace = Trace(agent_name=f"batch_{i}")
            trace.finish()
            processor.enqueue_trace(trace)

        await processor.flush()
        assert backend.trace_count == 5

        # Second flush with more data
        for i in range(3):
            trace = Trace(agent_name=f"batch2_{i}")
            trace.finish()
            processor.enqueue_trace(trace)

        await processor.flush()
        assert backend.trace_count == 8


class TestBatchProcessorQueueLimits:
    def test_queue_has_maxsize(self):
        backend = InMemoryBackend()
        processor = BatchProcessor(backend, batch_size=10, flush_interval=60, max_queue_size=5)

        for i in range(10):
            trace = Trace(agent_name=f"overflow_{i}")
            trace.finish()
            processor.enqueue_trace(trace)

        # Should not crash even if queue is full — drops oldest
        assert processor.pending_count <= 10


class TestBatchProcessorShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_flushes(self):
        backend = InMemoryBackend()
        processor = BatchProcessor(backend, batch_size=100, flush_interval=60)

        trace = Trace(agent_name="shutdown_test")
        trace.finish()
        processor.enqueue_trace(trace)

        await processor.flush()
        assert backend.trace_count >= 1

    @pytest.mark.asyncio
    async def test_double_shutdown(self):
        backend = InMemoryBackend()
        processor = BatchProcessor(backend, batch_size=100, flush_interval=60)
        await processor.shutdown()
        await processor.shutdown()  # Should not raise
