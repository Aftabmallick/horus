import atexit
import logging
import queue
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
import grpc

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.base import StorageBackend

from . import telemetry_pb2
from . import telemetry_pb2_grpc

logger = logging.getLogger(__name__)

class GrpcBackend(StorageBackend):
    def __init__(self, host: str, public_key: str, secret_key: str, max_queue_size: int = 10000):
        self.host = host.replace("http://", "").replace("https://", "")
        self.public_key = public_key
        self.secret_key = secret_key

        self.channel = grpc.insecure_channel(self.host)
        self.stub = telemetry_pb2_grpc.IngestionServiceStub(self.channel)

        self._queue = queue.Queue(maxsize=max_queue_size)
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="AgentTracer-GrpcWorker")
        self._worker_thread.start()

        atexit.register(self._sync_flush)

    def _get_metadata(self) -> tuple:
        return (
            ('x-public-key', self.public_key),
            ('authorization', f"Bearer {self.secret_key}")
        )

    def _enqueue(self, item_type: str, item_data: dict) -> None:
        try:
            self._queue.put_nowait((item_type, item_data))
        except queue.Full:
            logger.warning("AgentTracer gRPC queue is full! Dropping telemetry data.")

    def _worker_loop(self) -> None:
        batch_traces = []
        batch_spans = []
        last_send_time = time.time()

        while not self._stop_event.is_set():
            try:
                item_type, item_data = self._queue.get(timeout=1.0)
                if item_type == "trace":
                    batch_traces.append(item_data)
                elif item_type == "span":
                    batch_spans.append(item_data)
                self._queue.task_done()
            except queue.Empty:
                pass

            now = time.time()
            if len(batch_traces) >= 50 or len(batch_spans) >= 200 or (now - last_send_time) > 2.0:
                if batch_traces:
                    for trace in batch_traces:
                        self._send_trace(trace)
                    batch_traces = []
                if batch_spans:
                    for span in batch_spans:
                        self._send_span(span)
                    batch_spans = []
                last_send_time = now

        if batch_traces:
            for trace in batch_traces:
                self._send_trace(trace)
        if batch_spans:
            for span in batch_spans:
                self._send_span(span)

    def _send_trace(self, trace_data: dict) -> None:
        # Map from Trace.to_dict() to gRPC TracePayload
        payload = telemetry_pb2.TracePayload(
            trace_id=str(trace_data.get('trace_id', '')),
            session_id=str(trace_data.get('session_id', '')),
            project_id=str(trace_data.get('tenant_id', '')), # gRPC uses project_id
            tenant_id=str(trace_data.get('tenant_id', '')),
            trace_name=str(trace_data.get('agent_name', '')),
            status=str(trace_data.get('status', '')),
            start_time=str(trace_data.get('started_at', '')),
            end_time=str(trace_data.get('ended_at', '') or ''),
            input="", # Trace doesn't have input/output by default
            output="",
            error_message=str(trace_data.get('error', '')) if trace_data.get('error') else "",
            total_tokens=int(trace_data.get('total_tokens') or 0),
            total_cost=float(trace_data.get('total_cost') or 0.0)
        )
        try:
            print(f"[*] Sending gRPC TracePayload")
            self.stub.IngestTrace(payload, metadata=self._get_metadata())
        except grpc.RpcError as e:
            logger.warning(f"gRPC Trace ingestion error: {e}")

    def _send_span(self, span_data: dict) -> None:
        import json
        
        # Safe extraction for token_usage and cost_info dicts
        token_usage = span_data.get('token_usage') or {}
        total_tokens = token_usage.get('total_tokens', 0) if isinstance(token_usage, dict) else getattr(token_usage, 'total_tokens', 0)
        
        # Map from Span.to_dict() to gRPC SpanPayload
        payload = telemetry_pb2.SpanPayload(
            span_id=str(span_data.get('span_id', '')),
            trace_id=str(span_data.get('trace_id', '')),
            parent_id=str(span_data.get('parent_span_id', '') or ''),
            name=str(span_data.get('name', '')),
            span_type=str(span_data.get('span_type', '')),
            status=str(span_data.get('status', '')),
            start_time=str(span_data.get('started_at', '')),
            end_time=str(span_data.get('ended_at', '') or ''),
            input=json.dumps(span_data.get('input')) if span_data.get('input') is not None else "",
            output=json.dumps(span_data.get('output')) if span_data.get('output') is not None else "",
            error_message=json.dumps(span_data.get('error')) if span_data.get('error') is not None else "",
            total_tokens=int(total_tokens)
        )
        try:
            print(f"[*] Sending gRPC SpanPayload")
            self.stub.IngestSpan(payload, metadata=self._get_metadata())
        except grpc.RpcError as e:
            logger.warning(f"gRPC Span ingestion error: {e}")

    async def save_trace(self, trace: Trace) -> None:
        self._enqueue("trace", trace.to_dict())

    async def save_span(self, span: Span) -> None:
        self._enqueue("span", span.to_dict())

    async def save_spans_batch(self, spans: List[Span]) -> None:
        for span in spans:
            self._enqueue("span", span.to_dict())

    def _sync_flush(self) -> None:
        try:
            self._queue.join()
        except Exception:
            pass

    async def flush(self) -> None:
        self._sync_flush()

    async def close(self) -> None:
        self._sync_flush()
        self._stop_event.set()
        self._worker_thread.join(timeout=5.0)

    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        raise NotImplementedError("GrpcBackend is strictly for ingestion.")
    async def get_spans(self, trace_id: str) -> List[Span]:
        raise NotImplementedError("GrpcBackend is strictly for ingestion.")
    async def query_traces(self, filters: Dict[str, Any] | None = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        raise NotImplementedError("GrpcBackend is strictly for ingestion.")
    async def delete_traces(self, before: datetime) -> int:
        raise NotImplementedError("GrpcBackend is strictly for ingestion.")
    async def health_check(self) -> bool:
        return True
