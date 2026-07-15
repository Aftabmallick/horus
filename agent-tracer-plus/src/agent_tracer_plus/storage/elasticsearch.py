"""Elasticsearch storage backend for Agent Tracer Plus."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.base import StorageBackend

logger = logging.getLogger(__name__)

try:
    from elasticsearch import AsyncElasticsearch
    from elasticsearch.helpers import async_bulk
    HAS_ES = True
except ImportError:
    HAS_ES = False


class ElasticsearchStorage(StorageBackend):
    """Stores traces and spans in Elasticsearch."""

    def __init__(self, hosts: List[str] | str = "http://localhost:9200",
                 index_prefix: str = "agent-tracer"):
        if not HAS_ES:
            raise ImportError(
                "elasticsearch is required for Elasticsearch storage. "
                "Install it with: pip install elasticsearch[async]"
            )

        self.index_prefix = index_prefix
        self.traces_index = f"{index_prefix}-traces"
        self.spans_index = f"{index_prefix}-spans"

        if isinstance(hosts, str):
            hosts = [hosts]
        self.client = AsyncElasticsearch(hosts)

    async def _ensure_indices(self):
        """Create indices if they don't exist."""
        try:
            if not await self.client.indices.exists(index=self.traces_index):
                await self.client.indices.create(index=self.traces_index)
            if not await self.client.indices.exists(index=self.spans_index):
                await self.client.indices.create(index=self.spans_index)
        except Exception as e:
            logger.error(f"Failed to create indices: {e}")

    async def save_trace(self, trace: Trace) -> None:
        """Persist a completed trace."""
        try:
            await self.client.index(
                index=self.traces_index,
                id=trace.trace_id,
                document=trace.to_dict()
            )
        except Exception as e:
            logger.error(f"Failed to save trace to ES: {e}")

    async def save_span(self, span: Span) -> None:
        """Persist a completed span."""
        try:
            await self.client.index(
                index=self.spans_index,
                id=span.span_id,
                document=span.to_dict()
            )
        except Exception as e:
            logger.error(f"Failed to save span to ES: {e}")

    async def save_spans_batch(self, spans: List[Span]) -> None:
        """Persist a batch of spans efficiently."""
        if not spans:
            return

        actions = [
            {
                "_index": self.spans_index,
                "_id": span.span_id,
                "_source": span.to_dict(),
            }
            for span in spans
        ]

        try:
            await async_bulk(self.client, actions)
        except Exception as e:
            logger.error(f"Failed to bulk save spans to ES: {e}")

    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Retrieve a trace by ID."""
        try:
            resp = await self.client.get(index=self.traces_index, id=trace_id)
            if resp.get("found"):
                return Trace.from_dict(resp["_source"])
        except Exception as e:
            logger.debug(f"Trace {trace_id} not found or error: {e}")
        return None

    async def get_spans(self, trace_id: str) -> List[Span]:
        """Retrieve all spans for a trace."""
        try:
            resp = await self.client.search(
                index=self.spans_index,
                query={"term": {"trace_id.keyword": trace_id}},
                sort=[{"start_time": "asc"}],
                size=10000
            )
            return [Span.from_dict(hit["_source"]) for hit in resp["hits"]["hits"]]
        except Exception as e:
            logger.error(f"Failed to get spans for trace {trace_id}: {e}")
            return []

    async def query_traces(
        self,
        filters: Dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Query traces with optional filters."""
        es_query = {"match_all": {}}

        if filters:
            must_clauses = []
            for k, v in filters.items():
                must_clauses.append({"match": {k: v}})
            es_query = {"bool": {"must": must_clauses}}

        try:
            resp = await self.client.search(
                index=self.traces_index,
                query=es_query,
                sort=[{"start_time": "desc"}],
                from_=offset,
                size=limit
            )
            return [hit["_source"] for hit in resp["hits"]["hits"]]
        except Exception as e:
            logger.error(f"Failed to query traces: {e}")
            return []

    async def delete_traces(self, before: datetime) -> int:
        """Delete traces older than the given datetime."""
        time_str = before.isoformat()
        query = {"range": {"start_time": {"lt": time_str}}}

        try:
            # Delete spans first
            await self.client.delete_by_query(
                index=self.spans_index,
                query=query,
                conflicts="proceed"
            )
            # Then delete traces
            resp = await self.client.delete_by_query(
                index=self.traces_index,
                query=query,
                conflicts="proceed"
            )
            return resp.get("deleted", 0)
        except Exception as e:
            logger.error(f"Failed to delete old traces: {e}")
            return 0

    async def flush(self) -> None:
        """Elasticsearch async client handles flushes implicitly."""
        pass

    async def close(self) -> None:
        """Close the Elasticsearch client."""
        if hasattr(self, 'client'):
            await self.client.close()

    async def health_check(self) -> bool:
        """Check if Elasticsearch is reachable."""
        try:
            return await self.client.ping()
        except Exception as e:
            logger.error(f"Elasticsearch health check failed: {e}")
            return False
