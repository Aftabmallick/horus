"""Integration tests for NDJSONBackend — file persistence, CRUD, filtering."""

import os
import shutil
import pytest

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.ndjson import NDJSONBackend


@pytest.fixture
def ndjson_dir(tmp_path):
    d = str(tmp_path / "ndjson_test")
    yield d
    if os.path.exists(d):
        shutil.rmtree(d)


@pytest.fixture
def backend(ndjson_dir):
    return NDJSONBackend(directory=ndjson_dir)


class TestNDJSONSaveRetrieve:
    @pytest.mark.asyncio
    async def test_save_and_get_trace(self, backend):
        trace = Trace(agent_name="NDAgent", trace_id="t1")
        trace.finish()
        await backend.save_trace(trace)

        retrieved = await backend.get_trace("t1")
        assert retrieved is not None
        assert retrieved.agent_name == "NDAgent"

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


class TestNDJSONQuery:
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
        assert len(results) == 2


class TestNDJSONFilePersistence:
    @pytest.mark.asyncio
    async def test_data_persists_across_instances(self, ndjson_dir):
        # Write with first instance
        backend1 = NDJSONBackend(directory=ndjson_dir)
        trace = Trace(agent_name="Persist", trace_id="persist_1")
        trace.finish()
        await backend1.save_trace(trace)

        span = Span(name="persist_span", trace_id="persist_1", span_id="ps1")
        span.finish()
        await backend1.save_span(span)

        # Read with second instance
        backend2 = NDJSONBackend(directory=ndjson_dir)
        retrieved = await backend2.get_trace("persist_1")
        assert retrieved is not None
        assert retrieved.agent_name == "Persist"

        spans = await backend2.get_spans("persist_1")
        assert len(spans) == 1

    @pytest.mark.asyncio
    async def test_files_created(self, backend, ndjson_dir):
        trace = Trace(trace_id="t1")
        trace.finish()
        await backend.save_trace(trace)

        span = Span(name="s", trace_id="t1")
        span.finish()
        await backend.save_span(span)

        assert os.path.exists(os.path.join(ndjson_dir, "traces.jsonl"))
        assert os.path.exists(os.path.join(ndjson_dir, "spans.jsonl"))


class TestNDJSONSpanIsolation:
    @pytest.mark.asyncio
    async def test_get_spans_only_returns_matching_trace(self, backend):
        s1 = Span(name="s1", trace_id="trace_a", span_id="sa1")
        s1.finish()
        s2 = Span(name="s2", trace_id="trace_b", span_id="sb1")
        s2.finish()
        await backend.save_span(s1)
        await backend.save_span(s2)

        spans_a = await backend.get_spans("trace_a")
        assert len(spans_a) == 1
        assert spans_a[0].trace_id == "trace_a"


class TestNDJSONClose:
    @pytest.mark.asyncio
    async def test_close_is_noop(self, backend):
        await backend.close()  # Should not raise
