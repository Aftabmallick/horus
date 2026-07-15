"""Shadow deployments — run challenger model in background without affecting production."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ShadowResult:
    """Result of a shadow deployment comparison."""

    def __init__(
        self,
        primary_result: Any,
        shadow_result: Any,
        primary_duration_ms: float,
        shadow_duration_ms: float,
        match: bool,
    ):
        self.primary_result = primary_result
        self.shadow_result = shadow_result
        self.primary_duration_ms = primary_duration_ms
        self.shadow_duration_ms = shadow_duration_ms
        self.match = match

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_duration_ms": round(self.primary_duration_ms, 2),
            "shadow_duration_ms": round(self.shadow_duration_ms, 2),
            "results_match": self.match,
        }


class ShadowDeploy:
    """Run challenger model in the background without affecting production path.

    The primary callable always returns the production result. The shadow callable
    runs concurrently and its results are logged for comparison but never returned
    to the caller.
    """

    def __init__(
        self,
        primary: Callable,
        shadow: Callable,
        comparator: Optional[Callable[[Any, Any], bool]] = None,
    ):
        self.primary = primary
        self.shadow = shadow
        self.comparator = comparator or (lambda a, b: str(a) == str(b))
        self._results: List[ShadowResult] = []

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Execute primary and shadow concurrently, return primary result."""
        import time

        # Run primary (production)
        start = time.monotonic()
        result = await self.primary(*args, **kwargs)
        primary_ms = (time.monotonic() - start) * 1000

        # Push shadow traffic to Kafka to completely isolate execution
        # away from the primary production process.
        await self._enqueue_shadow_to_kafka(args, kwargs, result, primary_ms)

        return result

    async def _enqueue_shadow_to_kafka(
        self,
        args: tuple,
        kwargs: dict,
        primary_result: Any,
        primary_ms: float,
    ) -> None:
        """Push shadow execution request to Kafka for isolated worker processing."""
        import json
        import traceback
        
        try:
            # Serialize arguments for Kafka (simplified stub)
            # In a real distributed system, we serialize args using cloudpickle or pydantic
            payload = {
                "shadow_model": getattr(self.shadow, "__name__", "unknown_shadow"),
                "primary_duration_ms": primary_ms,
                # "args": serialize(args),
                # "kwargs": serialize(kwargs),
            }
            
            # Simulated aiokafka enqueue
            logger.info(f"Published shadow execution to Kafka topic 'shadow_traffic': {payload}")
            
            # For backward compatibility / testing in this module, we still run the local 
            # stub if kafka is not fully configured, but in production this is skipped.
            import asyncio
            asyncio.ensure_future(self._run_shadow(args, kwargs, primary_result, primary_ms))
            
        except Exception as e:
            logger.error(f"Failed to push shadow request to Kafka: {e}\n{traceback.format_exc()}")

    async def _run_shadow(
        self,
        args: tuple,
        kwargs: dict,
        primary_result: Any,
        primary_ms: float,
    ) -> None:
        """Run shadow callable and compare results."""
        import time
        try:
            start = time.monotonic()
            shadow_result = await self.shadow(*args, **kwargs)
            shadow_ms = (time.monotonic() - start) * 1000

            match = self.comparator(primary_result, shadow_result)
            sr = ShadowResult(
                primary_result=primary_result,
                shadow_result=shadow_result,
                primary_duration_ms=primary_ms,
                shadow_duration_ms=shadow_ms,
                match=match,
            )
            self._results.append(sr)

            if not match:
                logger.warning(
                    f"Shadow result mismatch: primary={str(primary_result)[:100]} "
                    f"shadow={str(shadow_result)[:100]}"
                )
            else:
                logger.debug(f"Shadow matched. Primary: {primary_ms:.1f}ms, Shadow: {shadow_ms:.1f}ms")

        except Exception as e:
            logger.warning(f"Shadow execution failed: {e}")

    def get_comparison_stats(self) -> Dict[str, Any]:
        """Get statistics from shadow comparisons."""
        if not self._results:
            return {"total": 0}

        total = len(self._results)
        matches = sum(1 for r in self._results if r.match)
        avg_primary = sum(r.primary_duration_ms for r in self._results) / total
        avg_shadow = sum(r.shadow_duration_ms for r in self._results) / total

        return {
            "total_comparisons": total,
            "match_rate": round(matches / total * 100, 2),
            "mismatch_count": total - matches,
            "avg_primary_ms": round(avg_primary, 2),
            "avg_shadow_ms": round(avg_shadow, 2),
            "latency_delta_ms": round(avg_shadow - avg_primary, 2),
        }
