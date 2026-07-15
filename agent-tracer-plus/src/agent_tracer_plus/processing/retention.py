"""Data retention TTL enforcement worker.

Automatically deletes traces older than configured TTL policies.
Can run as a background asyncio task or be triggered manually.

Usage::

    from agent_tracer_plus.processing.retention import RetentionEnforcer
    from agent_tracer_plus.processing.retention import RetentionPolicy

    policy = RetentionPolicy(
        default_ttl_days=90,
        error_ttl_days=365,
        debug_ttl_days=7,
    )
    enforcer = RetentionEnforcer(storage=backend, policy=policy)

    # Run once
    await enforcer.run_once()

    # Run as a background task (every 24h)
    task = enforcer.start_background_worker(interval_hours=24)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("agent_tracer_plus.processing.retention")


@dataclass
class RetentionPolicy:
    """Defines TTL (time-to-live) rules per trace category.

    Args:
        default_ttl_days: Default retention for all traces.
        error_ttl_days: Retention for traces with status=ERROR (longer — for debugging).
        debug_ttl_days: Retention for traces tagged as debug (shorter — reduce storage).
        custom_rules: Dict of {tag: ttl_days} for custom categories.
    """
    default_ttl_days: int = 90
    error_ttl_days: int = 365
    debug_ttl_days: int = 7
    custom_rules: Dict[str, int] = field(default_factory=dict)

    def cutoff_for(self, category: str = "default") -> datetime:
        """Return the cutoff datetime for a given category."""
        if category == "error":
            days = self.error_ttl_days
        elif category == "debug":
            days = self.debug_ttl_days
        else:
            days = self.custom_rules.get(category, self.default_ttl_days)
        return datetime.now(timezone.utc) - timedelta(days=days)


class RetentionEnforcer:
    """Enforces data retention TTL policies against a storage backend.

    Args:
        storage: A StorageBackend instance that implements delete_traces(before).
        policy: A RetentionPolicy specifying TTL rules.
        dry_run: If True, logs what would be deleted without actually deleting.
    """

    def __init__(
        self,
        storage: Any,
        policy: Optional[RetentionPolicy] = None,
        dry_run: bool = False,
    ) -> None:
        self.storage = storage
        self.policy = policy or RetentionPolicy()
        self.dry_run = dry_run
        self._task: Optional[asyncio.Task] = None

    async def run_once(self) -> Dict[str, int]:
        """Run retention enforcement once for all categories.

        Returns:
            Dict mapping category name to number of traces deleted.
        """
        results: Dict[str, int] = {}

        categories = ["default", "error", "debug"] + list(self.policy.custom_rules.keys())
        # Remove duplicates while preserving order
        seen = set()
        unique_categories = [c for c in categories if not (c in seen or seen.add(c))]

        for category in unique_categories:
            cutoff = self.policy.cutoff_for(category)
            if self.dry_run:
                logger.info(
                    f"[RetentionEnforcer DRY_RUN] Would delete '{category}' traces "
                    f"older than {cutoff.isoformat()}"
                )
                results[category] = 0
                continue

            try:
                deleted = await self.storage.delete_traces(before=cutoff)
                results[category] = deleted
                if deleted > 0:
                    logger.info(
                        f"[RetentionEnforcer] Deleted {deleted} '{category}' traces "
                        f"older than {cutoff.isoformat()}"
                    )
            except Exception as exc:
                logger.error(
                    f"[RetentionEnforcer] Failed to delete '{category}' traces: {exc}"
                )
                results[category] = -1

        return results

    def start_background_worker(self, interval_hours: float = 24.0) -> asyncio.Task:
        """Start retention enforcement as a recurring background asyncio task.

        Args:
            interval_hours: How often to run (default: every 24 hours).

        Returns:
            The asyncio.Task. Cancel it to stop the worker.
        """
        if self._task and not self._task.done():
            logger.warning("[RetentionEnforcer] Background worker already running.")
            return self._task

        async def _worker() -> None:
            logger.info(
                f"[RetentionEnforcer] Background worker started "
                f"(interval={interval_hours}h, dry_run={self.dry_run})"
            )
            while True:
                try:
                    results = await self.run_once()
                    total_deleted = sum(v for v in results.values() if v > 0)
                    logger.info(
                        f"[RetentionEnforcer] Cycle complete — deleted {total_deleted} traces total"
                    )
                except Exception as exc:
                    logger.error(f"[RetentionEnforcer] Worker cycle failed: {exc}")
                await asyncio.sleep(interval_hours * 3600)

        self._task = asyncio.create_task(_worker(), name="agent-tracer-retention-worker")
        return self._task

    def stop_background_worker(self) -> None:
        """Cancel the background worker task."""
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("[RetentionEnforcer] Background worker stopped.")
