"""Kafka storage backend for Agent Tracer Plus."""

import json
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.base import StorageBackend
from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("storage.kafka")

try:
    from aiokafka import AIOKafkaProducer
    HAS_KAFKA = True
except ImportError:
    HAS_KAFKA = False


class KafkaStorage(StorageBackend):
    """Sends traces and spans to Kafka topics asynchronously without blocking."""

    def __init__(self, bootstrap_servers: str = "localhost:9092",
                 traces_topic: str = "agent-tracer-traces",
                 spans_topic: str = "agent-tracer-spans",
                 queue_size: int = 10000):
        if not HAS_KAFKA:
            raise ImportError(
                "aiokafka is required for Kafka storage. "
                "Install it with: pip install aiokafka"
            )

        self.traces_topic = traces_topic
        self.spans_topic = spans_topic
        self.producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)
        self._started = False
        self._queue = asyncio.Queue(maxsize=queue_size)
        self._worker_task = None
        self._loop = None

    async def _ensure_started(self):
        if not self._started:
            await self.producer.start()
            self._started = True
            
        if self._worker_task is None:
            self._loop = asyncio.get_running_loop()
            self._worker_task = self._loop.create_task(self._publisher_worker())

    async def _publisher_worker(self):
        """Background task to continuously read from the queue and send to Kafka."""
        while True:
            try:
                item = await self._queue.get()
                if item is None:
                    # Sentinel value to shutdown
                    self._queue.task_done()
                    break
                    
                topic, key, value = item
                try:
                    # send() is non-blocking (returns a future), wait on it in background
                    await self.producer.send_and_wait(topic, key=key, value=value)
                except Exception as e:
                    logger.error(f"Failed to publish to Kafka topic {topic}: {e}")
                finally:
                    self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Kafka publisher worker: {e}")

    def _enqueue(self, topic: str, key: bytes, value: bytes):
        try:
            self._queue.put_nowait((topic, key, value))
        except asyncio.QueueFull:
            logger.error(f"Kafka publish queue is full. Dropping message for {topic}")

    async def save_trace(self, trace: Trace) -> None:
        """Send a completed trace to Kafka (non-blocking)."""
        await self._ensure_started()
        value = json.dumps(trace.to_dict()).encode("utf-8")
        key = trace.trace_id.encode("utf-8")
        self._enqueue(self.traces_topic, key, value)

    async def save_span(self, span: Span) -> None:
        """Send a completed span to Kafka (non-blocking)."""
        await self._ensure_started()
        value = json.dumps(span.to_dict()).encode("utf-8")
        key = span.trace_id.encode("utf-8")
        self._enqueue(self.spans_topic, key, value)

    async def save_spans_batch(self, spans: List[Span]) -> None:
        """Send a batch of spans to Kafka (non-blocking)."""
        await self._ensure_started()
        if not spans:
            return

        for span in spans:
            value = json.dumps(span.to_dict()).encode("utf-8")
            key = span.trace_id.encode("utf-8")
            self._enqueue(self.spans_topic, key, value)

    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        return None

    async def get_spans(self, trace_id: str) -> List[Span]:
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
        """Wait for the queue to empty and flush the producer."""
        if self._started:
            await self._queue.join()
            await self.producer.flush()

    async def close(self) -> None:
        """Close the Kafka producer."""
        if self._worker_task:
            try:
                self._queue.put_nowait(None)
                await asyncio.wait_for(self._worker_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.QueueFull):
                self._worker_task.cancel()
        
        if hasattr(self, 'producer') and self._started:
            await self.producer.stop()
            self._started = False

    async def health_check(self) -> bool:
        """Check if Kafka producer is ready."""
        try:
            await self._ensure_started()
            return True
        except Exception as e:
            logger.error(f"Kafka health check failed: {e}")
            return False
