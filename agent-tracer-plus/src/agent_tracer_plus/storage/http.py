"""Production HTTP Storage Backend for Agent Tracer Plus SaaS.

Uses a dedicated background thread and queue to ensure zero-overhead 
and resilience for the host application.
"""

import atexit
import json
import logging
import queue
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.base import StorageBackend

logger = logging.getLogger(__name__)

class HttpBackend(StorageBackend):
    """Sends traces over HTTP using a background worker thread."""

    def __init__(self, host: str, public_key: str, secret_key: str, max_queue_size: int = 10000):
        self.host = host.rstrip("/")
        self.public_key = public_key
        self.secret_key = secret_key

        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.secret_key}",
            "X-Public-Key": self.public_key,
            "User-Agent": "AgentTracerPlus-Python/0.1.0"
        }

        # Thread-safe queue for buffering traces/spans
        self._queue = queue.Queue(maxsize=max_queue_size)

        # Background worker state
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="AgentTracer-HttpWorker")
        self._worker_thread.start()

        # Ensure flush on exit
        atexit.register(self._sync_flush)

    def _enqueue(self, item_type: str, item_data: dict) -> None:
        """Non-blocking enqueue. Drops data if the queue is full (circuit breaker)."""
        try:
            self._queue.put_nowait((item_type, item_data))
        except queue.Full:
            logger.warning("AgentTracer queue is full! Dropping telemetry data to protect host memory.")

    def _worker_loop(self) -> None:
        """Dedicated background thread for batching and sending data."""
        batch_traces = []
        batch_spans = []
        last_send_time = time.time()

        while not self._stop_event.is_set():
            try:
                # Block for up to 1 second waiting for items
                item_type, item_data = self._queue.get(timeout=1.0)

                if item_type == "trace":
                    batch_traces.append(item_data)
                elif item_type == "span":
                    batch_spans.append(item_data)

                self._queue.task_done()
            except queue.Empty:
                pass

            # Send if batch is large enough or time elapsed
            now = time.time()
            if len(batch_traces) >= 50 or len(batch_spans) >= 200 or (now - last_send_time) > 2.0:
                if batch_traces:
                    self._send_with_retry("/api/ingest/traces", {"traces": batch_traces})
                    batch_traces = []
                if batch_spans:
                    self._send_with_retry("/api/ingest/spans", {"spans": batch_spans})
                    batch_spans = []
                last_send_time = now

        # Final flush on shutdown
        if batch_traces:
            self._send_with_retry("/api/ingest/traces", {"traces": batch_traces})
        if batch_spans:
            self._send_with_retry("/api/ingest/spans", {"spans": batch_spans})

    def _send_with_retry(self, endpoint: str, payload: dict) -> None:
        print(f"[*] Sending payload to {endpoint} with {len(payload)} items")
        """Sends data with exponential backoff for network resilience."""
        url = f"{self.host}{endpoint}"
        max_retries = 3
        backoff = 1.0

        data_bytes = json.dumps(payload).encode('utf-8')

        for attempt in range(max_retries):
            req = urllib.request.Request(url, data=data_bytes, headers=self._headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status in (200, 201, 202):
                        return
            except urllib.error.HTTPError as e:
                if e.code in (400, 401, 403):
                    # Fatal client errors, don't retry
                    logger.error(f"AgentTracer Fatal Auth/Request Error [{e.code}]: {e.read().decode()}")
                    return
                logger.warning(f"AgentTracer Server Error [{e.code}]. Retrying in {backoff}s...")
            except Exception as e:
                logger.warning(f"AgentTracer Connection Error: {e}. Retrying in {backoff}s...")

            time.sleep(backoff)
            backoff *= 2.0

        logger.error(f"AgentTracer dropped {len(payload.get('traces', []) + payload.get('spans', []))} items after {max_retries} retries.")

    # --- Async Storage Interface ---

    async def save_trace(self, trace: Trace) -> None:
        self._enqueue("trace", trace.to_dict())

    async def save_span(self, span: Span) -> None:
        self._enqueue("span", span.to_dict())

    async def save_spans_batch(self, spans: List[Span]) -> None:
        for span in spans:
            self._enqueue("span", span.to_dict())

    def _sync_flush(self) -> None:
        """Wait for the queue to empty before shutting down."""
        try:
            self._queue.join()
        except Exception:
            pass

    async def flush(self) -> None:
        self._sync_flush()

    async def close(self) -> None:
        self._stop_event.set()
        self._worker_thread.join(timeout=5.0)
        # Drain the queue directly if anything is left
        batch_traces = []
        batch_spans = []
        while not self._queue.empty():
            try:
                item_type, item_data = self._queue.get_nowait()
                if item_type == "trace":
                    batch_traces.append(item_data)
                elif item_type == "span":
                    batch_spans.append(item_data)
            except queue.Empty:
                break

        if batch_traces:
            self._send_with_retry("/api/ingest/traces", {"traces": batch_traces})
        if batch_spans:
            self._send_with_retry("/api/ingest/spans", {"spans": batch_spans})

    # --- Unsupported Query Methods ---
    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        raise NotImplementedError("HttpBackend is strictly for ingestion.")
    async def get_spans(self, trace_id: str) -> List[Span]:
        raise NotImplementedError("HttpBackend is strictly for ingestion.")
    async def query_traces(self, filters: Dict[str, Any] | None = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        raise NotImplementedError("HttpBackend is strictly for ingestion.")
    async def delete_traces(self, before: datetime) -> int:
        raise NotImplementedError("HttpBackend is strictly for ingestion.")
    async def health_check(self) -> bool:
        return True
