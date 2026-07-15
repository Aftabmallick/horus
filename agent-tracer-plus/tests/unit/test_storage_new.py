import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from agent_tracer_plus.storage.gcs import GCSBackend
from agent_tracer_plus.storage.azure_blob import AzureBlobBackend
from agent_tracer_plus.storage.kafka import KafkaStorage
from agent_tracer_plus.storage.redis_stream import RedisStreamStorage
from agent_tracer_plus.core.models import Trace

@pytest.mark.asyncio
async def test_gcs_backend_initialization():
    try:
        from gcloud.aio.storage import Storage
    except ImportError:
        pytest.skip("gcloud not installed")

    with patch('agent_tracer_plus.storage.gcs.Storage', create=True) as mock_storage:
        backend = GCSBackend(bucket="test-bucket")
        await backend._ensure_initialized()
        assert backend._initialized is True
        await backend.close()

@pytest.mark.asyncio
async def test_azure_blob_backend_initialization():
    try:
        from azure.storage.blob.aio import BlobServiceClient
    except ImportError:
        pytest.skip("azure not installed")

    with patch('agent_tracer_plus.storage.azure_blob.BlobServiceClient', create=True) as mock_blob:
        backend = AzureBlobBackend(connection_string="test_conn", container_name="test")
        await backend._ensure_initialized()
        assert backend._initialized is True
        await backend.close()

@pytest.mark.asyncio
async def test_kafka_backend_queue():
    with patch('agent_tracer_plus.storage.kafka.AIOKafkaProducer') as mock_producer:
        mock_producer_instance = AsyncMock()
        mock_producer.return_value = mock_producer_instance
        backend = KafkaStorage()
        await backend._ensure_started()
        assert backend._started is True
        
        # Test trace enqueue
        trace = Trace(trace_id="123", agent_name="test")
        await backend.save_trace(trace)
        assert not backend._queue.empty()
        
        await backend.close()

@pytest.mark.asyncio
async def test_redis_backend_queue():
    with patch('agent_tracer_plus.storage.redis_stream.redis.Redis') as mock_redis, patch('agent_tracer_plus.storage.redis_stream.redis.ConnectionPool.from_url'):
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        backend = RedisStreamStorage()
        await backend._start_worker_if_needed()
        
        # Mock the disconnect coroutine on the pool
        backend.pool = MagicMock()
        backend.pool.disconnect = AsyncMock()
        
        trace = Trace(trace_id="456", agent_name="test")
        await backend.save_trace(trace)
        assert not backend._queue.empty()
        
        await backend.close()
