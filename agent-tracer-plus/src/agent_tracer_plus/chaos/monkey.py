"""Chaos monkey engine."""

import asyncio
import builtins
import json
import logging
import random
from typing import List, Optional

from agent_tracer_plus.chaos.faults import (
    ErrorFault,
    LatencyFault,
    TokenExhaustionFault,
    HallucinationFault,
    NetworkPartitionFault,
    parse_faults,
    Fault
)

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    aioredis = None


class ChaosMonkey:
    """Injects failures to test agent resilience with Redis-backed config."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self._enabled = False
        self.faults: List[Fault] = []
        self._redis_client = None
        if HAS_REDIS:
            self._redis_client = aioredis.from_url(redis_url)
        self._redis_key = "atp:chaos:config"

    async def _sync_config(self):
        """Sync configuration from Redis."""
        if not self._redis_client:
            return

        try:
            config_json = await self._redis_client.get(self._redis_key)
            if config_json:
                config = json.loads(config_json)
                self._enabled = config.get("enabled", False)
                self.faults = parse_faults(config.get("faults", []))
            else:
                self._enabled = False
                self.faults = []
        except Exception as e:
            logger.debug(f"Failed to sync chaos config from Redis: {e}")

    async def enable(self, faults: List[dict]):
        self._enabled = True
        self.faults = parse_faults(faults)
        if self._redis_client:
            config = {"enabled": True, "faults": faults}
            await self._redis_client.set(self._redis_key, json.dumps(config))
        logger.warning("ChaosMonkey enabled! Faults will be injected.")

    async def disable(self):
        self._enabled = False
        self.faults = []
        if self._redis_client:
            config = {"enabled": False, "faults": []}
            await self._redis_client.set(self._redis_key, json.dumps(config))
        logger.info("ChaosMonkey disabled.")

    async def get_status(self) -> dict:
        """Return current chaos configuration status."""
        await self._sync_config()
        return {
            "enabled": self._enabled,
            "fault_count": len(self.faults),
            "faults": [
                {"type": type(f).__name__, "target": f.target, "probability": f.probability}
                for f in self.faults
            ]
        }

    async def inject(self, span_name: str) -> None:
        """Called by tracer instrumentors before execution (async path)."""
        await self._sync_config()
        await self._inject_faults(span_name)

    def inject_sync(self, span_name: str) -> None:
        """Called from sync span contexts — uses locally cached config only (no Redis sync)."""
        if not self._enabled:
            return
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule as a fire-and-forget — cannot block sync call
                loop.create_task(self._inject_faults(span_name))
            else:
                loop.run_until_complete(self._inject_faults(span_name))
        except Exception as e:
            logger.debug(f"ChaosMonkey inject_sync failed (non-fatal): {e}")

    async def _inject_faults(self, span_name: str) -> None:
        """Core fault injection logic."""
        if not self._enabled:
            return

        for fault in self.faults:
            # Wildcard or prefix matching
            target_clean = fault.target.replace("*", "")
            if fault.target == "*" or span_name.startswith(target_clean):
                if random.random() < fault.probability:
                    if isinstance(fault, LatencyFault):
                        logger.warning(f"[CHAOS] Injecting latency {fault.delay_ms}ms into '{span_name}'")
                        await asyncio.sleep(fault.delay_ms / 1000.0)

                    elif isinstance(fault, ErrorFault):
                        logger.warning(f"[CHAOS] Injecting error '{fault.exception_type}' into '{span_name}'")
                        exc_class = builtins.__dict__.get(fault.exception_type, RuntimeError)
                        if not (isinstance(exc_class, type) and issubclass(exc_class, BaseException)):
                            exc_class = RuntimeError
                        raise exc_class(fault.message)

                    elif isinstance(fault, NetworkPartitionFault):
                        logger.warning(f"[CHAOS] Injecting network partition into '{span_name}'")
                        raise ConnectionError(f"[ChaosMonkey] Simulated network partition in '{span_name}'")

                    elif isinstance(fault, HallucinationFault):
                        logger.warning(f"[CHAOS] Injecting hallucination response into '{span_name}'")
                        # HallucinationFault signals downstream code via exception with a special marker
                        raise fault.HallucinationInjected(fault.fake_response)

                    elif isinstance(fault, TokenExhaustionFault):
                        logger.warning(f"[CHAOS] Simulating token exhaustion in '{span_name}'")
                        # Nothing to raise — token exhaustion is simulated by returning early
                        # The instrumented span should detect max_tokens and set attribute

