"""Integration tests for the full SDK ingestion pipeline (SQLite E2E)."""

import asyncio
import pytest
import tempfile
import os

from agent_tracer_plus.core.models import Span, SpanType, Trace
from agent_tracer_plus.storage.sqlite import SQLiteBackend
from agent_tracer_plus.storage.memory import InMemoryBackend
from agent_tracer_plus.storage.composite import CompositeBackend


@pytest.mark.integration
class TestFullIngestionPipeline:
    """E2E pipeline: Trace → Span → SQLite → Query → Assert."""

    @pytest.mark.asyncio
    async def test_full_trace_span_pipeline(self):
        """Full pipeline: write trace+spans to SQLite, query back, verify data integrity."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            backend = SQLiteBackend(db_path=db_path)

            # 1. Write a trace
            trace = Trace(trace_id="pipeline-trace-001")
            trace.agent_name = "PipelineAgent"
            trace.service_name = "test-pipeline"
            trace.tenant_id = "tenant-pipeline"
            trace.status = "OK"
            trace.total_tokens = 800
            trace.total_cost = 0.04
            await backend.save_trace(trace)

            # 2. Write spans
            for i in range(3):
                span = Span(name=f"step_{i}", span_id=f"span-{i:03d}")
                span.trace_id = trace.trace_id
                span.span_type = SpanType.CUSTOM
                span.duration_ms = float(i * 10 + 5)
                await backend.save_span(span)

            # 3. Query the trace back
            results = await backend.query_traces(
                filters={"agent_name": "PipelineAgent"},
                limit=10,
            )
            assert len(results) == 1
            assert results[0]["trace_id"] == "pipeline-trace-001"
            assert results[0]["tenant_id"] == "tenant-pipeline"

            # 4. Query spans
            spans = await backend.get_spans("pipeline-trace-001")
            assert len(spans) == 3

            # 5. Health check
            healthy = await backend.health_check()
            assert healthy is True

        finally:
            await backend.close()
            for path in [db_path, db_path + "-shm", db_path + "-wal"]:
                if os.path.exists(path):
                    os.unlink(path)

    @pytest.mark.asyncio
    async def test_sql_injection_protection(self):
        """Malicious filter key must raise ValueError, not execute arbitrary SQL."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            backend = SQLiteBackend(db_path=db_path)
            with pytest.raises(ValueError, match="Invalid filter column"):
                await backend.query_traces(
                    filters={"1=1; DROP TABLE traces; --": "evil"}
                )
        finally:
            await backend.close()
            for path in [db_path, db_path + "-shm", db_path + "-wal"]:
                if os.path.exists(path):
                    os.unlink(path)

    @pytest.mark.asyncio
    async def test_composite_backend_fanout(self):
        """CompositeBackend must write to all backends and continue if one fails."""
        primary = InMemoryBackend()
        secondary = InMemoryBackend()
        composite = CompositeBackend(backends=[primary, secondary])

        trace = Trace(trace_id="composite-trace-001")
        trace.agent_name = "CompositeAgent"
        await composite.save_trace(trace)

        # Both backends must have the trace
        r1 = await primary.get_trace("composite-trace-001")
        r2 = await secondary.get_trace("composite-trace-001")
        assert r1 is not None
        assert r2 is not None
        assert r1.agent_name == "CompositeAgent"

    @pytest.mark.asyncio
    async def test_composite_backend_graceful_degradation(self):
        """If one backend fails, the other should still receive the data."""
        from unittest.mock import AsyncMock, MagicMock

        good_backend = InMemoryBackend()
        bad_backend = MagicMock()
        bad_backend.save_trace = AsyncMock(side_effect=RuntimeError("Storage down!"))

        composite = CompositeBackend(backends=[good_backend, bad_backend])

        trace = Trace(trace_id="degradation-trace-001")
        trace.agent_name = "ResilientAgent"

        # Should NOT raise — graceful degradation
        await composite.save_trace(trace)

        # Good backend must still have the data
        result = await good_backend.get_trace("degradation-trace-001")
        assert result is not None
        assert result.agent_name == "ResilientAgent"

    @pytest.mark.asyncio
    async def test_retention_delete_traces(self):
        """delete_traces should remove old traces and return correct count."""
        from datetime import datetime, timedelta, timezone

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            backend = SQLiteBackend(db_path=db_path)

            # Write 3 old traces (started 8 days ago)
            old_start = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
            for i in range(3):
                trace = Trace(trace_id=f"old-trace-{i:03d}")
                trace.agent_name = "OldAgent"
                trace._started_at = old_start  # Override started_at for test
                d = trace.to_dict()
                d["started_at"] = old_start
                await backend._ensure_initialized()
                await backend._db.execute(
                    """INSERT OR REPLACE INTO traces
                    (trace_id, execution_id, agent_name, service_name, session_id, tenant_id,
                     started_at, ended_at, duration_ms, status, metadata, tags,
                     total_tokens, total_cost, span_count, error_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        f"old-trace-{i:03d}", d["execution_id"], "OldAgent", "", "", "",
                        old_start, None, 0.0, "OK", "{}", "[]", 0, 0.0, 0, 0
                    )
                )
                await backend._db.commit()

            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            deleted = await backend.delete_traces(before=cutoff)
            assert deleted == 3

        finally:
            await backend.close()
            for path in [db_path, db_path + "-shm", db_path + "-wal"]:
                if os.path.exists(path):
                    os.unlink(path)
