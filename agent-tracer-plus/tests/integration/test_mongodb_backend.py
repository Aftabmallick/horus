"""Integration tests for MongoDB storage backend (mock-based, no real infra needed)."""

import pytest

from unittest.mock import AsyncMock, MagicMock, patch

pytest.importorskip("motor", reason="motor not installed")

from agent_tracer_plus.core.models import Span, SpanType, Trace


@pytest.fixture
def fake_trace():
    t = Trace(trace_id="mongo-trace-001")
    t.agent_name = "MongoAgent"
    t.service_name = "mongo-service"
    t.tenant_id = "tenant-xyz"
    t.status = "OK"
    t.total_tokens = 500
    t.total_cost = 0.02
    return t


@pytest.fixture
def fake_span(fake_trace):
    s = Span(name="mongo.span", span_id="mongo-span-001")
    s.trace_id = fake_trace.trace_id
    s.span_type = SpanType.TOOL
    s.duration_ms = 77.1
    return s


@pytest.mark.integration
class TestMongoDBBackendMocked:
    """Mocked integration tests for MongoDB backend."""

    def _make_backend(self):
        from agent_tracer_plus.storage.mongodb import MongoDBStorage
        backend = MongoDBStorage.__new__(MongoDBStorage)
        backend.uri = "mongodb://localhost:27017"
        backend._client = None
        backend._db = None
        return backend

    def test_trace_to_dict_schema(self, fake_trace):
        """Verify Trace.to_dict() produces MongoDB-compatible document."""
        data = fake_trace.to_dict()
        # MongoDB can store these natively
        assert isinstance(data["trace_id"], str)
        assert isinstance(data["total_tokens"], int)
        assert isinstance(data["total_cost"], float)
        assert isinstance(data["metadata"], dict)
        assert isinstance(data["tags"], list)

    def test_span_to_dict_schema(self, fake_span):
        """Verify Span.to_dict() produces MongoDB-compatible document."""
        data = fake_span.to_dict()
        assert data["span_id"] == "mongo-span-001"
        assert data["span_type"] == "TOOL"
        assert isinstance(data["attributes"], dict)
        assert isinstance(data["events"], list)

    @pytest.mark.asyncio
    async def test_health_check_fails_gracefully(self):
        """Health check should return False when no real MongoDB is available."""
        backend = self._make_backend()
        result = await backend.health_check()
        assert result is False

    def test_tenant_id_in_trace(self, fake_trace):
        """Tenant ID must survive serialization for multi-tenancy."""
        data = fake_trace.to_dict()
        assert data["tenant_id"] == "tenant-xyz"

    @pytest.mark.asyncio
    async def test_save_trace_requires_initialized_client(self):
        """save_trace should raise or handle gracefully if no client is available."""
        backend = self._make_backend()
        trace = Trace(trace_id="mongo-trace-err")
        with pytest.raises(Exception):
            # Without a real MongoDB, this must raise (not silently corrupt)
            await backend.save_trace(trace)
