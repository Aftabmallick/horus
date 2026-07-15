"""Integration tests for InMemoryBackend — CRUD, filtering, eviction, thread safety."""

import asyncio
import threading

import pytest

from agent_tracer_plus.core.models import Span, Trace, TokenUsage, CostInfo
from agent_tracer_plus.storage.memory import InMemoryBackend


@pytest.fixture
def backend():
    return InMemoryBackend()


class TestMemorySaveRetrieve:
    @pytest.mark.asyncio
    async def test_save_and_get_trace(self, backend):
        trace = Trace(agent_name="TestAgent", trace_id="t1")
        trace.finish()
        await backend.save_trace(trace)

        retrieved = await backend.get_trace("t1")
        assert retrieved is not None
        assert retrieved.agent_name == "TestAgent"

    @pytest.mark.asyncio
    async def test_get_nonexistent_trace(self, backend):
        result = await backend.get_trace("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_and_get_spans(self, backend):
        s1 = Span(name="step1", trace_id="t1", span_id="s1")
        s1.finish()
        s2 = Span(name="step2", trace_id="t1", span_id="s2")
        s2.finish()
        await backend.save_span(s1)
        await backend.save_span(s2)

        spans = await backend.get_spans("t1")
        assert len(spans) == 2

    @pytest.mark.asyncio
    async def test_save_spans_batch(self, backend):
        spans = [
            Span(name=f"span_{i}", trace_id="t1", span_id=f"s{i}")
            for i in range(5)
        ]
        for s in spans:
            s.finish()
        await backend.save_spans_batch(spans)
        retrieved = await backend.get_spans("t1")
        assert len(retrieved) == 5


class TestMemoryQuery:
    @pytest.mark.asyncio
    async def test_query_all(self, backend):
        for i in range(5):
            trace = Trace(agent_name=f"Agent{i}", trace_id=f"t{i}")
            trace.finish()
            await backend.save_trace(trace)

        results = await backend.query_traces()
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_query_with_filter(self, backend):
        t1 = Trace(agent_name="Alpha", trace_id="t1")
        t1.finish()
        t2 = Trace(agent_name="Beta", trace_id="t2")
        t2.finish()
        await backend.save_trace(t1)
        await backend.save_trace(t2)

        results = await backend.query_traces(filters={"agent_name": "Alpha"})
        assert len(results) == 1
        assert results[0]["agent_name"] == "Alpha"

    @pytest.mark.asyncio
    async def test_query_with_limit(self, backend):
        for i in range(10):
            trace = Trace(trace_id=f"t{i}")
            trace.finish()
            await backend.save_trace(trace)

        results = await backend.query_traces(limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_query_with_offset(self, backend):
        for i in range(10):
            trace = Trace(trace_id=f"t{i}")
            trace.finish()
            await backend.save_trace(trace)

        results = await backend.query_traces(limit=5, offset=8)
        assert len(results) == 2  # Only 2 traces left after offset 8


class TestMemoryEviction:
    @pytest.mark.asyncio
    async def test_evicts_oldest_at_max_capacity(self):
        backend = InMemoryBackend(max_traces=3)
        for i in range(5):
            trace = Trace(trace_id=f"t{i}")
            trace.finish()
            await backend.save_trace(trace)

        assert backend.trace_count == 3
        # Oldest traces should be evicted
        assert await backend.get_trace("t0") is None
        assert await backend.get_trace("t1") is None
        assert await backend.get_trace("t4") is not None


class TestMemoryDelete:
    @pytest.mark.asyncio
    async def test_delete_before(self, backend):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)

        old_trace = Trace(trace_id="old")
        old_trace.started_at = now - timedelta(days=10)
        old_trace.finish()
        await backend.save_trace(old_trace)

        new_trace = Trace(trace_id="new")
        new_trace.started_at = now
        new_trace.finish()
        await backend.save_trace(new_trace)

        deleted = await backend.delete_traces(before=now - timedelta(days=5))
        assert deleted == 1
        assert await backend.get_trace("old") is None
        assert await backend.get_trace("new") is not None


class TestMemoryConvenience:
    @pytest.mark.asyncio
    async def test_trace_count(self, backend):
        assert backend.trace_count == 0
        t = Trace(trace_id="t1")
        t.finish()
        await backend.save_trace(t)
        assert backend.trace_count == 1

    @pytest.mark.asyncio
    async def test_span_count(self, backend):
        assert backend.span_count == 0
        s = Span(name="s", trace_id="t1")
        s.finish()
        await backend.save_span(s)
        assert backend.span_count == 1

    @pytest.mark.asyncio
    async def test_get_all_traces(self, backend):
        t1 = Trace(trace_id="t1")
        t1.finish()
        t2 = Trace(trace_id="t2")
        t2.finish()
        await backend.save_trace(t1)
        await backend.save_trace(t2)
        all_traces = backend.get_all_traces()
        assert len(all_traces) == 2

    @pytest.mark.asyncio
    async def test_get_all_spans(self, backend):
        for i in range(3):
            s = Span(name=f"s{i}", trace_id="t1")
            s.finish()
            await backend.save_span(s)
        all_spans = backend.get_all_spans()
        assert len(all_spans) == 3


class TestMemoryThreadSafety:
    @pytest.mark.asyncio
    async def test_concurrent_writes(self, backend):
        """Multiple threads writing simultaneously should not corrupt data."""
        errors = []

        async def writer(prefix, count):
            for i in range(count):
                trace = Trace(trace_id=f"{prefix}_{i}")
                trace.finish()
                try:
                    await backend.save_trace(trace)
                except Exception as e:
                    errors.append(e)

        # Run 5 concurrent writers with 20 traces each
        await asyncio.gather(
            writer("a", 20),
            writer("b", 20),
            writer("c", 20),
            writer("d", 20),
            writer("e", 20),
        )

        assert errors == []
        assert backend.trace_count == 100


class TestMemoryHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check(self, backend):
        assert await backend.health_check() is True


class TestMemoryClose:
    @pytest.mark.asyncio
    async def test_close_clears_data(self, backend):
        t = Trace(trace_id="t1")
        t.finish()
        await backend.save_trace(t)
        s = Span(name="s", trace_id="t1")
        s.finish()
        await backend.save_span(s)

        await backend.close()
        assert backend.trace_count == 0
        assert backend.span_count == 0
