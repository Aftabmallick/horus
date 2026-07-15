"""Webhook storage backend for Agent Tracer Plus."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.base import StorageBackend

logger = logging.getLogger(__name__)

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


class WebhookStorage(StorageBackend):
    """Sends traces and spans to an HTTP webhook."""

    def __init__(self, endpoint: str, headers: Dict[str, str] | None = None,
                 timeout: float = 5.0):
        if not HAS_HTTPX:
            raise ImportError(
                "httpx is required for Webhook storage. "
                "Install it with: pip install httpx"
            )

        self.endpoint = endpoint
        self.headers = headers or {"Content-Type": "application/json"}
        self.client = httpx.AsyncClient(timeout=timeout, headers=self.headers)

    async def save_trace(self, trace: Trace) -> None:
        """Send a completed trace to the webhook."""
        try:
            payload = {"type": "trace", "data": trace.to_dict()}
            response = await self.client.post(self.endpoint, json=payload)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send trace to webhook: {e}")

    async def save_span(self, span: Span) -> None:
        """Send a completed span to the webhook."""
        try:
            payload = {"type": "span", "data": span.to_dict()}
            response = await self.client.post(self.endpoint, json=payload)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send span to webhook: {e}")

    async def save_spans_batch(self, spans: List[Span]) -> None:
        """Send a batch of spans to the webhook."""
        if not spans:
            return

        try:
            payload = {
                "type": "span_batch",
                "data": [span.to_dict() for span in spans]
            }
            response = await self.client.post(self.endpoint, json=payload)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send span batch to webhook: {e}")

    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Webhook is a write-only sink."""
        return None

    async def get_spans(self, trace_id: str) -> List[Span]:
        """Webhook is a write-only sink."""
        return []

    async def query_traces(
        self,
        filters: Dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Webhook is a write-only sink."""
        return []

    async def delete_traces(self, before: datetime) -> int:
        """Webhook is a write-only sink."""
        return 0

    async def flush(self) -> None:
        """Flush not applicable for simple webhook."""
        pass

    async def close(self) -> None:
        """Close the httpx client."""
        if hasattr(self, 'client'):
            await self.client.aclose()

    async def health_check(self) -> bool:
        """Check if webhook endpoint is reachable via HEAD or GET request."""
        try:
            response = await self.client.head(self.endpoint)
            return response.status_code < 500
        except Exception as e:
            logger.error(f"Webhook health check failed: {e}")
            return False
