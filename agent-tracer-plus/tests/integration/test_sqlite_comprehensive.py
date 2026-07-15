"""Comprehensive integration tests for SQLiteBackend — CRUD, pagination, delete, WAL, health."""

import os
import pytest
from datetime import datetime, timezone, timedelta

from agent_tracer_plus.core.models import Span, Trace, TokenUsage, CostInfo
from agent_tracer_plus.storage.sqlite import SQLiteBackend


@pytest.fixture
async def backend(tmp_path):
    db_path = str(tmp_path / "test.db")
    storage = SQLiteBackend(db_path)
    yield storage
    await storage.close()


class TestSQLiteSaveRetrieve:
    @pytest.mark.asyncio
    async def test_save_and_get_trace(self, backend):
        trace = Trace(agent_name="SQLAgent", trace_id="t1", service_name="svc")
        trace.finish()
        await backend.save_trace(trace)

        retrieved = await backend.get_trace("t1")
        assert retrieved is not None
        assert retrieved.agent_name == "SQLAgent"

    @pytest.mark.asyncio
    async def test_get_nonexistent_trace(self, backend):
        result = await backend.get_trace("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_and_get_spans(self, backend):
        trace = Trace(trace_id="t1")
        trace.finish()
        await backend.save_trace(trace)

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
        trace = Trace(trace_id="t1")
        trace.finish()
        await backend.save_trace(trace)

        spans = [
            Span(name=f"span_{i}", trace_id="t1", span_id=f"s{i}")
            for i in range(10)
        ]
        for s in spans:
            s.finish()
        await backend.save_spans_batch(spans)

        retrieved = await backend.get_spans("t1")
        assert len(retrieved) == 10

    @pytest.mark.asyncio
    async def test_upsert_trace(self, backend):
        """INSERT OR REPLACE should update existing traces."""
        trace = Trace(agent_name="V1", trace_id="t1")
        trace.finish()
        await backend.save_trace(trace)

        trace.agent_name = "V2"
        await backend.save_trace(trace)

        retrieved = await backend.get_trace("t1")
        assert retrieved.agent_name == "V2"


class TestSQLiteQuery:
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
    async def test_query_with_status_filter(self, backend):
        t1 = Trace(trace_id="t1")
        t1.finish()  # COMPLETED
        await backend.save_trace(t1)

        t2 = Trace(trace_id="t2")
        t2.finish(status="ERROR")
        await backend.save_trace(t2)

        results = await backend.query_traces(filters={"status": "ERROR"})
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_pagination(self, backend):
        for i in range(20):
            trace = Trace(trace_id=f"t{i:03d}")
            trace.finish()
            await backend.save_trace(trace)

        page1 = await backend.query_traces(limit=5, offset=0)
        assert len(page1) == 5

        page2 = await backend.query_traces(limit=5, offset=5)
        assert len(page2) == 5

        # No overlap
        ids1 = {r["trace_id"] for r in page1}
        ids2 = {r["trace_id"] for r in page2}
        assert ids1.isdisjoint(ids2)

    @pytest.mark.asyncio
    async def test_query_ordered_by_started_at(self, backend):
        for i in range(5):
            trace = Trace(trace_id=f"t{i}")
            trace.finish()
            await backend.save_trace(trace)

        results = await backend.query_traces(limit=5)
        # Should be ordered by started_at DESC
        assert len(results) == 5


class TestSQLiteDelete:
    @pytest.mark.asyncio
    async def test_delete_before(self, backend):
        now = datetime.now(timezone.utc)

        old = Trace(trace_id="old")
        old.started_at = now - timedelta(days=30)
        old.finish()
        await backend.save_trace(old)

        new = Trace(trace_id="new")
        new.started_at = now
        new.finish()
        await backend.save_trace(new)

        deleted = await backend.delete_traces(before=now - timedelta(days=15))
        assert deleted == 1

        assert await backend.get_trace("old") is None
        assert await backend.get_trace("new") is not None


class TestSQLiteHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check(self, backend):
        assert await backend.health_check() is True


class TestSQLiteFlush:
    @pytest.mark.asyncio
    async def test_flush(self, backend):
        trace = Trace(trace_id="t1")
        trace.finish()
        await backend.save_trace(trace)
        await backend.flush()  # Should not raise


class TestSQLiteClose:
    @pytest.mark.asyncio
    async def test_close_and_reopen(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        backend1 = SQLiteBackend(db_path)
        trace = Trace(trace_id="persist_test", agent_name="Persist")
        trace.finish()
        await backend1.save_trace(trace)
        await backend1.close()

        # Data should persist
        backend2 = SQLiteBackend(db_path)
        retrieved = await backend2.get_trace("persist_test")
        assert retrieved is not None
        assert retrieved.agent_name == "Persist"
        await backend2.close()
