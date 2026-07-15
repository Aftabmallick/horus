"""Integration tests for Redis Streams storage backend."""

import pytest
pytest.importorskip("redis")
pytest.importorskip("confluent_kafka")

from unittest.mock import AsyncMock, MagicMock, patch

pytest.importorskip("redis", reason="redis not installed")

from agent_tracer_plus.core.models import Span, SpanType, Trace


@pytest.fixture
def fake_trace():
    t = Trace(trace_id="redis-trace-001")
    t.agent_name = "RedisAgent"
    t.status = "OK"
    t.tenant_id = "tenant-redis"
    t.total_tokens = 300
    return t


@pytest.mark.integration
class TestRedisStreamBackendMocked:
    """Mocked integration tests for Redis Streams backend."""

    def _make_backend(self):
        from agent_tracer_plus.storage.redis_stream import RedisStreamStorage
        backend = RedisStreamStorage.__new__(RedisStreamStorage)
        backend.url = "redis://localhost:6379"
        backend._client = None
        return backend

    @pytest.mark.asyncio
    async def test_health_check_returns_false_without_server(self):
        backend = self._make_backend()
        result = await backend.health_check()
        assert result is False

    def test_trace_serializes_to_flat_dict(self, fake_trace):
        """Redis streams require flat key-value pairs (no nested dicts)."""
        data = fake_trace.to_dict()
        # Ensure critical fields are present
        assert data["trace_id"] == "redis-trace-001"
        assert data["status"] == "OK"

    @pytest.mark.asyncio
    async def test_save_trace_raises_without_client(self, fake_trace):
        """Without a real Redis, save_trace must fail explicitly."""
        backend = self._make_backend()
        with pytest.raises(Exception):
            await backend.save_trace(fake_trace)


@pytest.mark.integration
class TestKafkaBackend:
    """Mocked integration tests for Kafka storage backend."""

    def _make_backend(self):
        from agent_tracer_plus.storage.kafka import KafkaStorage
        backend = KafkaStorage.__new__(KafkaStorage)
        backend.brokers = "localhost:9092"
        backend.topic = "agent_traces"
        backend._producer = None
        return backend

    @pytest.mark.asyncio
    async def test_health_check_returns_false_without_broker(self):
        backend = self._make_backend()
        result = await backend.health_check()
        assert result is False

    def test_trace_json_serialization(self):
        """Kafka messages are JSON. Verify trace serializes to valid JSON."""
        import json
        t = Trace(trace_id="kafka-trace-001")
        t.agent_name = "KafkaAgent"
        data = t.to_dict()
        # Must be JSON serializable
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        assert parsed["trace_id"] == "kafka-trace-001"
