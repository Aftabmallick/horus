"""MongoDB storage backend for Agent Tracer Plus."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.base import StorageBackend

logger = logging.getLogger(__name__)

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    HAS_MOTOR = True
except ImportError:
    HAS_MOTOR = False


class MongoDBStorage(StorageBackend):
    """Stores traces and spans in MongoDB using motor."""

    def __init__(self, uri: str = "mongodb://localhost:27017/agent_tracer",
                 db_name: str = "agent_tracer",
                 max_pool_size: int = 100):
        if not HAS_MOTOR:
            raise ImportError(
                "motor is required for MongoDB storage. "
                "Install it with: pip install motor"
            )

        parsed = urlparse(uri)
        if parsed.path and len(parsed.path) > 1:
            self.db_name = parsed.path.lstrip('/')
        else:
            self.db_name = db_name

        self.client = AsyncIOMotorClient(uri, maxPoolSize=max_pool_size)
        self.db = self.client[self.db_name]
        self.traces_collection = self.db.traces
        self.spans_collection = self.db.spans

    async def _ensure_indexes(self):
        """Create necessary indexes."""
        await self.traces_collection.create_index("trace_id", unique=True)
        await self.spans_collection.create_index("trace_id")
        await self.spans_collection.create_index("span_id", unique=True)
        await self.traces_collection.create_index("start_time")
        await self.spans_collection.create_index("start_time")
        await self.spans_collection.create_index("span_type")

    async def save_trace(self, trace: Trace) -> None:
        """Persist a completed trace."""
        trace_dict = trace.to_dict()
        await self.traces_collection.update_one(
            {"trace_id": trace.trace_id},
            {"$set": trace_dict},
            upsert=True
        )

    async def save_span(self, span: Span) -> None:
        """Persist a completed span."""
        span_dict = span.to_dict()
        await self.spans_collection.update_one(
            {"span_id": span.span_id},
            {"$set": span_dict},
            upsert=True
        )

    async def save_spans_batch(self, spans: List[Span]) -> None:
        """Persist a batch of spans efficiently."""
        if not spans:
            return

        from pymongo import UpdateOne
        requests = [
            UpdateOne(
                {"span_id": span.span_id},
                {"$set": span.to_dict()},
                upsert=True
            )
            for span in spans
        ]
        if requests:
            await self.spans_collection.bulk_write(requests, ordered=False)

    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Retrieve a trace by ID."""
        doc = await self.traces_collection.find_one({"trace_id": trace_id})
        if doc:
            doc.pop("_id", None)
            return Trace.from_dict(doc)
        return None

    async def get_spans(self, trace_id: str) -> List[Span]:
        """Retrieve all spans for a trace."""
        cursor = self.spans_collection.find({"trace_id": trace_id}).sort("start_time", 1)
        spans = []
        async for doc in cursor:
            doc.pop("_id", None)
            spans.append(Span.from_dict(doc))
        return spans

    async def query_traces(
        self,
        filters: Dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Query traces with optional filters."""
        query = {}
        if filters:
            for k, v in filters.items():
                if isinstance(v, dict):
                    # pass through mongodb operators like $gt, $lt
                    query[k] = v
                else:
                    query[k] = v

        cursor = self.traces_collection.find(query).sort("start_time", -1).skip(offset).limit(limit)
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    async def delete_traces(self, before: datetime) -> int:
        """Delete traces and spans older than the given datetime."""
        # Find traces to delete
        cursor = self.traces_collection.find(
            {"start_time": {"$lt": before.isoformat()}},
            {"trace_id": 1}
        )
        trace_ids = []
        async for doc in cursor:
            trace_ids.append(doc["trace_id"])

        if not trace_ids:
            return 0

        # Delete spans associated with those traces
        await self.spans_collection.delete_many({"trace_id": {"$in": trace_ids}})
        # Delete traces
        result = await self.traces_collection.delete_many({"trace_id": {"$in": trace_ids}})
        return result.deleted_count

    async def flush(self) -> None:
        """MongoDB motor client handles flushes implicitly."""
        pass

    async def close(self) -> None:
        """Close the MongoDB client."""
        if hasattr(self, 'client'):
            self.client.close()

    async def health_check(self) -> bool:
        """Check if MongoDB is reachable."""
        try:
            await self.client.admin.command('ping')
            return True
        except Exception as e:
            logger.error(f"MongoDB health check failed: {e}")
            return False
