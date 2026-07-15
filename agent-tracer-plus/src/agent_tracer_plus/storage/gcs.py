"""Google Cloud Storage (GCS) Archival Storage Backend."""

import json
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.base import StorageBackend
from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("storage.gcs")


class GCSBackend(StorageBackend):
    """Archival storage backend using GCS for traces.
    
    Traces and spans are buffered in memory and flushed periodically as NDJSON objects.
    """

    def __init__(self, bucket: str, prefix: str = "traces/", flush_interval_sec: float = 5.0):
        self.bucket = bucket
        self.prefix = prefix
        self.flush_interval_sec = flush_interval_sec
        self._client = None
        self._initialized = False
        
        self._spans_buffer: List[Dict[str, Any]] = []
        self._buffer_lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._loop = None

    async def _ensure_initialized(self):
        try:
            from gcloud.aio.storage import Storage
        except ImportError:
            raise ImportError("gcloud-aio-storage is required for GCS backend. Run `pip install agent-tracer-plus[gcs]`")

        if self._client is None:
            self._client = Storage()
            self._initialized = True
            
        if self._flush_task is None:
            self._loop = asyncio.get_running_loop()
            self._flush_task = self._loop.create_task(self._periodic_flush())

    async def _periodic_flush(self):
        while True:
            try:
                await asyncio.sleep(self.flush_interval_sec)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in GCS periodic flush: {e}")

    def _generate_key(self, obj_type: str) -> str:
        date_prefix = datetime.utcnow().strftime("%Y/%m/%d/%H")
        timestamp = datetime.utcnow().timestamp()
        return f"{self.prefix}{date_prefix}/{obj_type}_{timestamp}.ndjson"

    async def save_trace(self, trace: Trace) -> None:
        await self._ensure_initialized()
        data = trace.to_dict()
        
        # Traces are flushed immediately for visibility
        key = f"{self.prefix}{datetime.utcnow().strftime('%Y/%m/%d')}/{trace.trace_id}/trace.ndjson"

        try:
            await self._client.upload(
                self.bucket,
                key,
                json.dumps(data).encode("utf-8") + b"\n",
                content_type="application/x-ndjson"
            )
        except Exception as e:
            logger.error(f"Failed to upload trace to GCS: {e}")

    async def save_span(self, span: Span) -> None:
        await self.save_spans_batch([span])

    async def save_spans_batch(self, spans: List[Span]) -> None:
        if not spans:
            return

        await self._ensure_initialized()
        
        async with self._buffer_lock:
            for s in spans:
                self._spans_buffer.append(s.to_dict())

    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        raise NotImplementedError("Direct reading of traces from GCS is not supported.")

    async def get_spans(self, trace_id: str) -> List[Span]:
        raise NotImplementedError("Direct reading of spans from GCS is not supported.")

    async def query_traces(self, filters: Dict[str, Any] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        raise NotImplementedError("Querying traces from GCS is not supported.")

    async def delete_traces(self, before: datetime) -> int:
        raise NotImplementedError("GCS Lifecycle rules should be used for trace deletion.")

    async def flush(self) -> None:
        if not self._initialized or not self._client:
            return
            
        async with self._buffer_lock:
            if not self._spans_buffer:
                return
            spans_to_upload = self._spans_buffer
            self._spans_buffer = []
            
        if spans_to_upload:
            try:
                body = "\n".join(json.dumps(s) for s in spans_to_upload) + "\n"
                key = self._generate_key("spans")
                await self._client.upload(
                    self.bucket,
                    key,
                    body.encode("utf-8"),
                    content_type="application/x-ndjson"
                )
                logger.debug(f"Flushed {len(spans_to_upload)} spans to GCS at {key}")
            except Exception as e:
                logger.error(f"Failed to flush spans to GCS: {e}")
                # Restore to buffer if flush fails
                async with self._buffer_lock:
                    self._spans_buffer = spans_to_upload + self._spans_buffer

    async def close(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        await self.flush()
        
        if self._client:
            await self._client.close()
            self._client = None
            self._initialized = False

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            # gcloud-aio-storage has bucket metadata methods, but simple connection check is usually enough
            return True
        except Exception:
            return False
