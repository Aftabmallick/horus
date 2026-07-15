"""Azure Blob Storage Archival Backend."""

import json
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.base import StorageBackend
from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("storage.azure")


class AzureBlobBackend(StorageBackend):
    """Archival storage backend using Azure Blob Storage for traces.
    
    Traces and spans are buffered in memory and flushed periodically as NDJSON objects.
    """

    def __init__(self, connection_string: str, container_name: str, prefix: str = "traces/", flush_interval_sec: float = 5.0):
        self.connection_string = connection_string
        self.container_name = container_name
        self.prefix = prefix
        self.flush_interval_sec = flush_interval_sec
        self._blob_service_client = None
        self._container_client = None
        self._initialized = False
        
        self._spans_buffer: List[Dict[str, Any]] = []
        self._buffer_lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._loop = None

    async def _ensure_initialized(self):
        try:
            from azure.storage.blob.aio import BlobServiceClient
        except ImportError:
            raise ImportError("azure-storage-blob is required for Azure backend. Run `pip install agent-tracer-plus[azure]`")

        if self._blob_service_client is None:
            self._blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
            self._container_client = self._blob_service_client.get_container_client(self.container_name)
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
                logger.error(f"Error in Azure Blob periodic flush: {e}")

    def _generate_blob_name(self, obj_type: str) -> str:
        date_prefix = datetime.utcnow().strftime("%Y/%m/%d/%H")
        timestamp = datetime.utcnow().timestamp()
        return f"{self.prefix}{date_prefix}/{obj_type}_{timestamp}.ndjson"

    async def save_trace(self, trace: Trace) -> None:
        await self._ensure_initialized()
        data = trace.to_dict()
        
        # Traces are flushed immediately for visibility
        blob_name = f"{self.prefix}{datetime.utcnow().strftime('%Y/%m/%d')}/{trace.trace_id}/trace.ndjson"

        try:
            blob_client = self._container_client.get_blob_client(blob_name)
            await blob_client.upload_blob(json.dumps(data).encode("utf-8") + b"\n", overwrite=True)
        except Exception as e:
            logger.error(f"Failed to upload trace to Azure Blob: {e}")

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
        raise NotImplementedError("Direct reading of traces from Azure Blob is not supported.")

    async def get_spans(self, trace_id: str) -> List[Span]:
        raise NotImplementedError("Direct reading of spans from Azure Blob is not supported.")

    async def query_traces(self, filters: Dict[str, Any] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        raise NotImplementedError("Querying traces from Azure Blob is not supported.")

    async def delete_traces(self, before: datetime) -> int:
        raise NotImplementedError("Azure Blob Lifecycle rules should be used for trace deletion.")

    async def flush(self) -> None:
        if not self._initialized or not self._container_client:
            return
            
        async with self._buffer_lock:
            if not self._spans_buffer:
                return
            spans_to_upload = self._spans_buffer
            self._spans_buffer = []
            
        if spans_to_upload:
            try:
                body = "\n".join(json.dumps(s) for s in spans_to_upload) + "\n"
                blob_name = self._generate_blob_name("spans")
                blob_client = self._container_client.get_blob_client(blob_name)
                await blob_client.upload_blob(body.encode("utf-8"), overwrite=True)
                logger.debug(f"Flushed {len(spans_to_upload)} spans to Azure Blob at {blob_name}")
            except Exception as e:
                logger.error(f"Failed to flush spans to Azure Blob: {e}")
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
        
        if self._blob_service_client:
            await self._blob_service_client.close()
            self._blob_service_client = None
            self._container_client = None
            self._initialized = False

    async def health_check(self) -> bool:
        if not self._container_client:
            return False
        try:
            await self._container_client.get_container_properties()
            return True
        except Exception:
            return False
