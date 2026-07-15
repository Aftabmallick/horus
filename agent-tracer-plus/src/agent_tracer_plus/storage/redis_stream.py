"""Redis Stream storage backend for Agent Tracer Plus."""

import json
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.base import StorageBackend
from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("storage.redis")

try:
    import redis.asyncio as redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


class RedisStreamStorage(StorageBackend):
    """Stores traces and spans in Redis Streams asynchronously without blocking."""

    def __init__(self, url: str = "redis://localhost:6379/0",
                 stream_prefix: str = "agent_tracer",
                 max_len: int = 100000,
                 queue_size: int = 10000,
                 batch_size: int = 100,
                 flush_interval_sec: float = 1.0):
        if not HAS_REDIS:
            raise ImportError(
                "redis is required for Redis Stream storage. "
                "Install it with: pip install redis"
            )

        # Use a connection pool for efficiency
        self.pool = redis.ConnectionPool.from_url(url, max_connections=10)
        self.client = redis.Redis(connection_pool=self.pool)
        self.traces_stream = f"{stream_prefix}:traces"
        self.spans_stream = f"{stream_prefix}:spans"
        self.max_len = max_len
        self.batch_size = batch_size
        self.flush_interval_sec = flush_interval_sec
        
        self._queue = asyncio.Queue(maxsize=queue_size)
        self._worker_task = None
        self._loop = None

    async def _start_worker_if_needed(self):
        if self._worker_task is None:
            self._loop = asyncio.get_running_loop()
            self._worker_task = self._loop.create_task(self._publisher_worker())

    async def _publisher_worker(self):
        batch = []
        while True:
            try:
                # Wait for items or flush interval
                try:
                    item = await asyncio.wait_for(self._queue.get(), timeout=self.flush_interval_sec)
                    if item is None:
                        self._queue.task_done()
                        if batch:
                            await self._flush_batch(batch)
                        break
                    batch.append(item)
                    self._queue.task_done()
                except asyncio.TimeoutError:
                    pass
                
                if len(batch) >= self.batch_size or (batch and self._queue.empty()):
                    await self._flush_batch(batch)
                    batch = []
                    
            except asyncio.CancelledError:
                if batch:
                    await self._flush_batch(batch)
                break
            except Exception as e:
                logger.error(f"Error in Redis publisher worker: {e}")

    async def _flush_batch(self, batch: List[tuple]):
        try:
            async with self.client.pipeline() as pipe:
                for stream, data in batch:
                    pipe.xadd(stream, {"data": data}, maxlen=self.max_len)
                await pipe.execute()
        except Exception as e:
            logger.error(f"Failed to publish batch to Redis streams: {e}")

    def _enqueue(self, stream: str, data: str):
        try:
            self._queue.put_nowait((stream, data))
        except asyncio.QueueFull:
            logger.error(f"Redis publish queue is full. Dropping message for {stream}")

    async def save_trace(self, trace: Trace) -> None:
        """Publish a completed trace to the Redis Stream."""
        await self._start_worker_if_needed()
        self._enqueue(self.traces_stream, json.dumps(trace.to_dict()))

    async def save_span(self, span: Span) -> None:
        """Publish a completed span to the Redis Stream."""
        await self._start_worker_if_needed()
        self._enqueue(self.spans_stream, json.dumps(span.to_dict()))

    async def save_spans_batch(self, spans: List[Span]) -> None:
        """Persist a batch of spans efficiently."""
        if not spans:
            return
            
        await self._start_worker_if_needed()
        for span in spans:
            self._enqueue(self.spans_stream, json.dumps(span.to_dict()))

    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        logger.warning("get_trace is not efficient on RedisStreamStorage")
        return None

    async def get_spans(self, trace_id: str) -> List[Span]:
        logger.warning("get_spans is not efficient on RedisStreamStorage")
        return []

    async def query_traces(
        self,
        filters: Dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        return []

    async def delete_traces(self, before: datetime) -> int:
        return 0

    async def flush(self) -> None:
        await self._queue.join()

    async def close(self) -> None:
        if self._worker_task:
            try:
                self._queue.put_nowait(None)
                await asyncio.wait_for(self._worker_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.QueueFull):
                self._worker_task.cancel()
        
        if hasattr(self, 'pool'):
            await self.pool.disconnect()

    async def health_check(self) -> bool:
        try:
            return await self.client.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
