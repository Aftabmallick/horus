"""Feedback collection — Redis-backed persistence for RLHF pipelines."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    aioredis = None


class FeedbackCollector:
    """Collect human feedback for traces with Redis-backed persistence.

    Usage:
        collector = FeedbackCollector()
        await collector.add_feedback(
            trace_id="abc123",
            score=0.2,
            label="bad",
            correction="The answer should have been X, not Y.",
            annotator="alice@corp.com"
        )
        # Export RLHF training data
        async for record in collector.export_training_data(min_score=0.5):
            print(record)  # JSONL record ready for fine-tuning
    """

    _KEY_PREFIX = "atp:feedback"
    _INDEX_KEY = "atp:feedback:__index__"

    def __init__(self, redis_url: Optional[str] = None):
        self._redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._client: Optional[Any] = None
        # In-memory fallback when Redis is unavailable
        self._local_store: Dict[str, List[dict]] = {}

    def _get_client(self) -> Optional[Any]:
        if not HAS_REDIS:
            return None
        if self._client is None:
            self._client = aioredis.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def add_feedback(
        self,
        trace_id: str,
        score: float,
        label: str,
        correction: Optional[str] = None,
        annotator: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add human feedback for a trace.

        Args:
            trace_id: The trace to annotate.
            score: 0.0 (worst) to 1.0 (best).
            label: Human-readable label e.g. "good", "bad", "needs_correction".
            correction: Optional corrected output text (used for RLHF).
            annotator: Email/ID of the person providing feedback.
            metadata: Any additional key-value pairs.
        """
        record = {
            "trace_id": trace_id,
            "score": score,
            "label": label,
            "correction": correction,
            "annotator": annotator,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        client = self._get_client()
        if client:
            try:
                key = f"{self._KEY_PREFIX}:{trace_id}"
                await client.rpush(key, json.dumps(record))
                # 90-day TTL
                await client.expire(key, 60 * 60 * 24 * 90)
                # Add to global index for export scanning
                await client.sadd(self._INDEX_KEY, trace_id)
                logger.debug(f"Feedback persisted to Redis for trace {trace_id}")
            except Exception as e:
                logger.warning(f"Redis feedback write failed, using local fallback: {e}")
                self._local_store.setdefault(trace_id, []).append(record)
        else:
            logger.debug("Redis unavailable, storing feedback in-memory")
            self._local_store.setdefault(trace_id, []).append(record)

    async def get_feedback(self, trace_id: str) -> List[dict]:
        """Retrieve all feedback entries for a trace."""
        client = self._get_client()
        if client:
            try:
                key = f"{self._KEY_PREFIX}:{trace_id}"
                raw = await client.lrange(key, 0, -1)
                return [json.loads(r) for r in raw]
            except Exception as e:
                logger.warning(f"Redis feedback read failed: {e}")
        return self._local_store.get(trace_id, [])

    async def export_training_data(
        self,
        min_score: float = 0.0,
        max_score: float = 1.0,
        label_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Export feedback as RLHF training records.

        Filters by score range and optional label. Returns a list of dicts
        ready for fine-tuning pipelines (e.g., OpenAI fine-tune format).

        Args:
            min_score: Minimum score to include (inclusive).
            max_score: Maximum score to include (inclusive).
            label_filter: If set, only return feedback with this label.

        Returns:
            List of RLHF-ready training records.
        """
        records = []
        client = self._get_client()

        if client:
            try:
                trace_ids = await client.smembers(self._INDEX_KEY)
            except Exception as e:
                logger.warning(f"Redis index scan failed: {e}")
                trace_ids = list(self._local_store.keys())
        else:
            trace_ids = list(self._local_store.keys())

        for trace_id in trace_ids:
            entries = await self.get_feedback(trace_id)
            for entry in entries:
                score = entry.get("score", 0.0)
                label = entry.get("label", "")

                if not (min_score <= score <= max_score):
                    continue
                if label_filter and label != label_filter:
                    continue

                records.append({
                    "trace_id": trace_id,
                    "score": score,
                    "label": label,
                    "correction": entry.get("correction"),
                    "annotator": entry.get("annotator"),
                    "created_at": entry.get("created_at"),
                    "metadata": entry.get("metadata", {}),
                })

        return records

    async def summary(self) -> Dict[str, Any]:
        """Return aggregate feedback statistics."""
        all_records = await self.export_training_data()
        if not all_records:
            return {"total": 0, "avg_score": 0.0, "label_distribution": {}}

        scores = [r["score"] for r in all_records]
        label_dist: Dict[str, int] = {}
        for r in all_records:
            label_dist[r["label"]] = label_dist.get(r["label"], 0) + 1

        return {
            "total": len(all_records),
            "avg_score": round(sum(scores) / len(scores), 3),
            "min_score": min(scores),
            "max_score": max(scores),
            "label_distribution": label_dist,
        }

