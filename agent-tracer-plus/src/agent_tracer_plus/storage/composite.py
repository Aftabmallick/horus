"""Composite storage backend (fan-out) with circuit breaker protection.

Allows writing traces to multiple storage backends simultaneously.
For example, writing to local SQLite for fast queries, and S3 for archiving.

If a secondary backend fails repeatedly, its circuit breaker opens and it is
temporarily skipped — protecting throughput and preventing cascading failures.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.base import StorageBackend
from agent_tracer_plus.storage.resilience import CircuitBreaker, CircuitBreakerOpenError
from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("storage.composite")


class CompositeBackend(StorageBackend):
    """Writes data to multiple backends simultaneously with circuit breaker protection.

    Reads (queries, get) are served from the primary (first) backend.

    Args:
        backends: List of storage backends. First is primary (reads + writes).
        failure_threshold: Failures before opening a secondary backend's circuit.
        recovery_timeout: Seconds before attempting recovery on an open circuit.
    """

    def __init__(
        self,
        backends: List[StorageBackend],
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> None:
        if not backends:
            raise ValueError("CompositeBackend requires at least one backend.")
        self.backends = backends
        self._primary = backends[0]

        # Create a circuit breaker for each secondary backend
        self._breakers: Dict[int, CircuitBreaker] = {}
        for i, backend in enumerate(backends[1:], start=1):
            self._breakers[i] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                name=type(backend).__name__,
            )

    async def _fan_out(self, method_name: str, *args: Any) -> None:
        """Fan out a write operation to all backends with graceful degradation."""
        primary_coro = getattr(self._primary, method_name)(*args)
        try:
            await primary_coro
        except Exception as exc:
            logger.error(
                f"[CompositeBackend] PRIMARY {type(self._primary).__name__}.{method_name} "
                f"failed: {exc}. Data may be lost!"
            )
            raise  # Primary failure is re-raised — this is not recoverable

        # Secondary backends: fail silently (graceful degradation)
        for i, backend in enumerate(self.backends[1:], start=1):
            breaker = self._breakers[i]
            coro_func = getattr(backend, method_name)
            try:
                await breaker.call(coro_func, *args)
            except CircuitBreakerOpenError as e:
                logger.debug(f"[CompositeBackend] {e} — skipping secondary write")
            except Exception as exc:
                logger.warning(
                    f"[CompositeBackend] Secondary {type(backend).__name__}.{method_name} "
                    f"failed: {exc} — primary data preserved"
                )

    async def save_trace(self, trace: Trace) -> None:
        await self._fan_out("save_trace", trace)

    async def save_span(self, span: Span) -> None:
        await self._fan_out("save_span", span)

    async def save_spans_batch(self, spans: List[Span]) -> None:
        await self._fan_out("save_spans_batch", spans)

    # Reads are served from the primary backend
    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        return await self._primary.get_trace(trace_id)

    async def get_spans(self, trace_id: str) -> List[Span]:
        return await self._primary.get_spans(trace_id)

    async def query_traces(
        self, filters: Dict[str, Any] | None = None, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        return await self._primary.query_traces(filters, limit, offset)

    async def delete_traces(self, before: datetime) -> int:
        # Delete from all backends, but return the primary's count
        tasks = [b.delete_traces(before) for b in self.backends]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        primary_res = results[0]
        if isinstance(primary_res, Exception):
            logger.error(f"Primary backend failed to delete traces: {primary_res}")
            return 0
        return primary_res

    async def flush(self) -> None:
        tasks = [b.flush() for b in self.backends]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self) -> None:
        tasks = [b.close() for b in self.backends]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def health_check(self) -> bool:
        # Healthy if primary is healthy
        return await self._primary.health_check()

    async def health_check_all(self) -> Dict[str, Any]:
        """Return health and circuit breaker state for all backends."""
        results = {}
        for i, backend in enumerate(self.backends):
            name = type(backend).__name__
            try:
                healthy = await backend.health_check()
            except Exception:
                healthy = False
            entry: Dict[str, Any] = {
                "healthy": healthy,
                "role": "primary" if i == 0 else "secondary",
            }
            if i in self._breakers:
                entry["circuit_breaker"] = self._breakers[i].stats()
            results[f"{name}_{i}"] = entry
        return results

