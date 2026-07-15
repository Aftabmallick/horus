"""Session tracking — groups traces into user sessions via context propagation."""

import contextvars
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Context variable to propagate session_id to all child traces
_current_session: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "atp_current_session", default=None
)

try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    aioredis = None


def get_current_session() -> Optional[Dict[str, Any]]:
    """Return the active session dict, or None."""
    return _current_session.get()


class SessionTracker:
    """Groups agent traces into a user session with automatic context propagation.

    Usage:
        async with SessionTracker(session_id="sess_abc", user_id="user_123") as session:
            # All traces created here are automatically tagged with session_id
            result = await agent.run("What is the weather?")
            result2 = await agent.run("What about tomorrow?")
        # Session is finalized — total cost, trace count etc. available

    Also supports manual tracking:
        tracker = SessionTracker(user_id="user_123")
        track_session(tracker.session_id, tracker.user_id)
    """

    _KEY_PREFIX = "atp:sessions"

    def __init__(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        redis_url: Optional[str] = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())
        self.user_id = user_id or ""
        self.metadata = metadata or {}
        self._redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._client: Optional[Any] = None
        self._token: Optional[contextvars.Token] = None
        self._started_at = datetime.now(timezone.utc)
        self._trace_ids: List[str] = []

    def _get_client(self) -> Optional[Any]:
        if not HAS_REDIS:
            return None
        if self._client is None:
            self._client = aioredis.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def __aenter__(self) -> "SessionTracker":
        session_data = {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "started_at": self._started_at.isoformat(),
            "metadata": self.metadata,
        }
        self._token = _current_session.set(session_data)

        # Store session in Redis for cross-process visibility
        client = self._get_client()
        if client:
            try:
                key = f"{self._KEY_PREFIX}:{self.session_id}"
                await client.hset(key, mapping={
                    "session_id": self.session_id,
                    "user_id": self.user_id,
                    "started_at": self._started_at.isoformat(),
                    "status": "active",
                })
                await client.expire(key, 60 * 60 * 24 * 30)  # 30-day TTL
                # Add to global index
                await client.sadd(f"{self._KEY_PREFIX}:__index__", self.session_id)
                logger.debug(f"Session {self.session_id} started for user {self.user_id}")
            except Exception as e:
                logger.warning(f"Redis session write failed: {e}")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        ended_at = datetime.now(timezone.utc)
        duration_ms = (ended_at - self._started_at).total_seconds() * 1000

        client = self._get_client()
        if client:
            try:
                key = f"{self._KEY_PREFIX}:{self.session_id}"
                await client.hset(key, mapping={
                    "ended_at": ended_at.isoformat(),
                    "duration_ms": str(round(duration_ms, 2)),
                    "status": "error" if exc_type else "completed",
                })
                logger.debug(f"Session {self.session_id} finalized ({round(duration_ms)}ms)")
            except Exception as e:
                logger.warning(f"Redis session finalize failed: {e}")

        if self._token is not None:
            _current_session.reset(self._token)

        return None  # Don't suppress exceptions

    async def record_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Record a named event in this session (for funnel/drop-off tracking)."""
        client = self._get_client()
        if client:
            try:
                import json
                event = {
                    "name": name,
                    "session_id": self.session_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "attributes": attributes or {},
                }
                key = f"{self._KEY_PREFIX}:{self.session_id}:events"
                await client.rpush(key, json.dumps(event))
                await client.expire(key, 60 * 60 * 24 * 30)
            except Exception as e:
                logger.warning(f"Redis session event write failed: {e}")


def track_session(session_id: str, user_id: str) -> None:
    """Attach the current trace to a session (simple one-liner for existing code).
    
    Works outside of the async context manager for backwards compatibility.
    """
    from agent_tracer_plus.core.context import get_current_trace
    trace = get_current_trace()
    if trace:
        trace.metadata["session_id"] = session_id
        trace.metadata["user_id"] = user_id
        logger.debug(f"Linked trace {trace.trace_id} to session {session_id}")
    else:
        logger.debug("track_session called with no active trace — no-op")


def inject_session_into_trace(trace: Any) -> None:
    """Called by the tracer engine to auto-inject session context into new traces."""
    session = get_current_session()
    if session and trace:
        trace.metadata.setdefault("session_id", session.get("session_id", ""))
        trace.metadata.setdefault("user_id", session.get("user_id", ""))
        trace.session_id = session.get("session_id", "")

