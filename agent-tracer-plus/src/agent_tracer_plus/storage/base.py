"""Abstract base class for all storage backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_tracer_plus.core.models import Span, Trace


class StorageBackend(ABC):
    """Base class for trace/span storage.

    All backends must implement these methods.
    Methods are async to support both sync and async backends uniformly.
    """

    @abstractmethod
    async def save_trace(self, trace: Trace) -> None:
        """Persist a completed trace."""
        ...

    @abstractmethod
    async def save_span(self, span: Span) -> None:
        """Persist a completed span."""
        ...

    @abstractmethod
    async def save_spans_batch(self, spans: List[Span]) -> None:
        """Persist a batch of spans. Default: iterate save_span."""
        for span in spans:
            await self.save_span(span)

    @abstractmethod
    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Retrieve a trace by ID."""
        ...

    @abstractmethod
    async def get_spans(self, trace_id: str) -> List[Span]:
        """Retrieve all spans for a trace."""
        ...

    @abstractmethod
    async def query_traces(
        self,
        filters: Dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Query traces with optional filters. Returns dicts."""
        ...

    @abstractmethod
    async def delete_traces(self, before: datetime) -> int:
        """Delete traces older than the given datetime. Returns count deleted."""
        ...

    @abstractmethod
    async def flush(self) -> None:
        """Flush any buffered data to persistent storage."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources (connections, file handles)."""
        ...

    async def health_check(self) -> bool:
        """Check if the backend is healthy and reachable."""
        return True
