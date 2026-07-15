"""Token and cost budget enforcement with real-time per-minute rate limiting.

Supports:
- Per-trace token/cost limits (raises BudgetExceededError when on_exceed='kill')
- Per-minute sliding window rate limiting
- Per-tenant budget isolation
- Async task cancellation on budget kill
"""

from __future__ import annotations

import asyncio
import collections
import time
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional, Tuple

from agent_tracer_plus.core.models import Trace
from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("budget")


class BudgetExceededError(Exception):
    """Raised when a trace exceeds its configured budget."""
    pass


@dataclass
class TokenBudget:
    """Budget configuration for a trace or agent."""
    # Per-trace limits
    max_tokens_per_trace: Optional[int] = None
    max_cost_per_trace: Optional[float] = None

    # Per-minute rate limits (sliding window)
    max_tokens_per_minute: Optional[int] = None
    max_cost_per_minute: Optional[float] = None

    # Action when budget exceeded
    on_exceed: str = "kill"  # "alert" | "kill" | "log"

    # Per-tenant tracking key (empty = global)
    tenant_id: str = ""


@dataclass
class _WindowEntry:
    """A timestamped usage entry for the sliding window."""
    timestamp: float
    tokens: int
    cost: float


class BudgetEnforcer:
    """Enforces token and cost limits during a trace's lifecycle.

    Supports:
    - Per-trace limits checked at trace completion
    - Per-minute sliding window rate limits checked per span
    - Per-tenant isolation via tenant_id buckets
    """

    def __init__(self, budget: TokenBudget) -> None:
        self.budget = budget
        # Sliding window: tenant_id -> deque of _WindowEntry
        self._window: Dict[str, Deque[_WindowEntry]] = collections.defaultdict(
            lambda: collections.deque()
        )
        self._lock = asyncio.Lock()

    # ── Per-Trace Enforcement ────────────────────────────────────────────────

    def check_budget(self, trace: Trace) -> None:
        """Check the current usage against per-trace limits.

        Called synchronously after a trace completes.
        Raises BudgetExceededError if on_exceed == 'kill' and limits crossed.
        """
        exceeded, reason = self._evaluate_trace(trace)

        if exceeded:
            msg = f"Budget threshold crossed for trace {trace.trace_id}: {reason}"
            if self.budget.on_exceed == "kill":
                logger.error(msg)
                # Cancel the current asyncio task if running
                self._try_cancel_current_task()
                raise BudgetExceededError(msg)
            elif self.budget.on_exceed == "alert":
                logger.warning(f"ALERT: {msg}")
            else:
                logger.info(msg)

    def _evaluate_trace(self, trace: Trace) -> Tuple[bool, str]:
        """Evaluate trace usage against configured limits. Returns (exceeded, reason)."""
        exceeded = False
        reasons = []

        total_tokens = getattr(trace, "total_tokens", 0) or 0
        total_cost = getattr(trace, "total_cost", 0.0) or 0.0

        if self.budget.max_tokens_per_trace is not None and total_tokens > self.budget.max_tokens_per_trace:
            exceeded = True
            reasons.append(
                f"Token limit exceeded: {total_tokens:,} > {self.budget.max_tokens_per_trace:,}"
            )

        if self.budget.max_cost_per_trace is not None and total_cost > self.budget.max_cost_per_trace:
            exceeded = True
            reasons.append(
                f"Cost limit exceeded: ${total_cost:.4f} > ${self.budget.max_cost_per_trace:.4f}"
            )

        return exceeded, " AND ".join(reasons)

    @staticmethod
    def _try_cancel_current_task() -> None:
        """Attempt to cancel the current asyncio task for hard budget kills."""
        try:
            task = asyncio.current_task()
            if task:
                task.cancel()
        except RuntimeError:
            pass  # No running event loop — sync code path, BudgetExceededError is sufficient

    # ── Per-Minute Sliding Window ─────────────────────────────────────────────

    async def check_rate_limit(self, tokens: int, cost: float, tenant_id: str = "") -> None:
        """Check per-minute rate limits using a sliding window.

        Call this after each LLM span completes (inside the batch processor or tracer).
        Raises BudgetExceededError if on_exceed='kill' and rate limit crossed.

        Args:
            tokens: Tokens used by the just-completed span.
            cost: Cost of the just-completed span.
            tenant_id: Tenant identifier for isolation.
        """
        if self.budget.max_tokens_per_minute is None and self.budget.max_cost_per_minute is None:
            return  # No rate limits configured

        key = tenant_id or self.budget.tenant_id or "__global__"
        now = time.monotonic()
        window_start = now - 60.0

        async with self._lock:
            window = self._window[key]

            # Evict entries older than 1 minute
            while window and window[0].timestamp < window_start:
                window.popleft()

            # Add current usage
            window.append(_WindowEntry(timestamp=now, tokens=tokens, cost=cost))

            # Sum window
            window_tokens = sum(e.tokens for e in window)
            window_cost = sum(e.cost for e in window)

        # Check limits
        exceeded = False
        reasons = []

        if self.budget.max_tokens_per_minute is not None and window_tokens > self.budget.max_tokens_per_minute:
            exceeded = True
            reasons.append(
                f"Token rate exceeded: {window_tokens:,}/min > {self.budget.max_tokens_per_minute:,}/min"
            )

        if self.budget.max_cost_per_minute is not None and window_cost > self.budget.max_cost_per_minute:
            exceeded = True
            reasons.append(
                f"Cost rate exceeded: ${window_cost:.4f}/min > ${self.budget.max_cost_per_minute:.4f}/min"
            )

        if exceeded:
            msg = f"Rate limit exceeded for tenant '{key}': {' AND '.join(reasons)}"
            if self.budget.on_exceed == "kill":
                logger.error(msg)
                self._try_cancel_current_task()
                raise BudgetExceededError(msg)
            elif self.budget.on_exceed == "alert":
                logger.warning(f"ALERT: {msg}")
            else:
                logger.info(msg)

    # ── Per-Tenant Stats ──────────────────────────────────────────────────────

    async def get_usage_stats(self, tenant_id: str = "") -> Dict[str, float]:
        """Return current sliding-window usage stats for a tenant."""
        key = tenant_id or self.budget.tenant_id or "__global__"
        now = time.monotonic()
        window_start = now - 60.0

        async with self._lock:
            window = self._window.get(key, collections.deque())
            recent = [e for e in window if e.timestamp >= window_start]

        return {
            "window_tokens": sum(e.tokens for e in recent),
            "window_cost_usd": round(sum(e.cost for e in recent), 6),
            "window_span_count": len(recent),
            "max_tokens_per_minute": self.budget.max_tokens_per_minute,
            "max_cost_per_minute": self.budget.max_cost_per_minute,
        }
