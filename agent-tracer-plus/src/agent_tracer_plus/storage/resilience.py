"""Circuit breaker for storage backend resilience.

Implements the standard CLOSED → OPEN → HALF_OPEN state machine
to prevent cascading failures when a storage backend is unavailable.

Usage::

    from agent_tracer_plus.storage.resilience import CircuitBreaker

    breaker = CircuitBreaker(
        failure_threshold=5,
        recovery_timeout=30.0,
        name="clickhouse",
    )

    async def save():
        async with breaker:
            await real_backend.save_trace(trace)
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger("agent_tracer_plus.storage.resilience")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"       # Normal operation — requests pass through
    OPEN = "OPEN"           # Failing — requests are rejected immediately
    HALF_OPEN = "HALF_OPEN" # Recovery probe — one request allowed through


class CircuitBreakerOpenError(Exception):
    """Raised when a request is rejected because the circuit is OPEN."""


class CircuitBreaker:
    """Async circuit breaker for storage backend calls.

    Args:
        failure_threshold: Number of consecutive failures before opening circuit.
        recovery_timeout: Seconds to wait before attempting a recovery probe (HALF_OPEN).
        success_threshold: Consecutive successes in HALF_OPEN to return to CLOSED.
        name: Human-readable name for logging.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        success_threshold: int = 2,
        name: str = "storage",
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.name = name

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at: Optional[float] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def is_closed(self) -> bool:
        return self._state == CircuitState.CLOSED

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt a recovery probe."""
        if self._opened_at is None:
            return False
        return (time.monotonic() - self._opened_at) >= self.recovery_timeout

    async def _on_success(self) -> None:
        async with self._lock:
            self._failure_count = 0
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    logger.info(
                        f"[CircuitBreaker:{self.name}] Recovery confirmed — returning to CLOSED"
                    )
                    self._state = CircuitState.CLOSED
                    self._success_count = 0
                    self._opened_at = None

    async def _on_failure(self, exc: Exception) -> None:
        async with self._lock:
            self._failure_count += 1
            self._success_count = 0

            if self._state == CircuitState.HALF_OPEN:
                logger.warning(
                    f"[CircuitBreaker:{self.name}] Recovery probe failed ({exc}) — "
                    f"reopening circuit"
                )
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()

            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    logger.error(
                        f"[CircuitBreaker:{self.name}] {self._failure_count} consecutive failures — "
                        f"opening circuit for {self.recovery_timeout}s"
                    )
                    self._state = CircuitState.OPEN
                    self._opened_at = time.monotonic()

    async def call(self, coro_func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute a coroutine through the circuit breaker.

        Args:
            coro_func: An async callable to execute.
            *args, **kwargs: Arguments forwarded to `coro_func`.

        Raises:
            CircuitBreakerOpenError: If the circuit is OPEN.
            Any exception raised by `coro_func`.
        """
        # Transition from OPEN to HALF_OPEN if recovery timeout elapsed
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    logger.info(
                        f"[CircuitBreaker:{self.name}] Attempting recovery probe (HALF_OPEN)"
                    )
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                else:
                    remaining = self.recovery_timeout - (
                        time.monotonic() - (self._opened_at or 0)
                    )
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Recovery in ~{remaining:.1f}s"
                    )

        try:
            result = await coro_func(*args, **kwargs)
            await self._on_success()
            return result
        except CircuitBreakerOpenError:
            raise
        except Exception as exc:
            await self._on_failure(exc)
            raise

    def reset(self) -> None:
        """Manually reset the circuit to CLOSED state (for testing/admin use)."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at = None
        logger.info(f"[CircuitBreaker:{self.name}] Manually reset to CLOSED")

    def stats(self) -> dict:
        """Return current circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "opened_at": self._opened_at,
        }
