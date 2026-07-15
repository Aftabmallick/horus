"""Auto-patcher — monkey-patches installed libraries for zero-code tracing.

Uses the InstrumentorRegistry for dynamic discovery of installed packages
and applies only the patches for packages that are actually installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from agent_tracer_plus.auto.registry import default_registry
from agent_tracer_plus.utils.logger import get_logger
import random
import asyncio
import time

if TYPE_CHECKING:
    from agent_tracer_plus.core.config import TracerConfig

logger = get_logger("auto.patcher")


class ChaosException(Exception):
    """Exception injected by the Chaos Engineering module."""
    pass


class AutoPatcher:
    """Detects installed packages and applies instrumentation patches."""
    
    _global_chaos_config = None # Used by wrap() to inject faults

    def __init__(self, config: TracerConfig) -> None:
        self._config = config
        self._patched: List[str] = []
        if getattr(config, "chaos_enabled", False):
            AutoPatcher._global_chaos_config = config

    def patch_all(self) -> None:
        """Apply all applicable patches based on config and installed packages.

        Uses the global InstrumentorRegistry to discover and apply patches
        for all installed packages.
        """
        self._patched = default_registry.apply_all(self._config)


def wrap(target: object, method_name: str, wrapper: object) -> None:
    """Replace a method on a target object with a wrapper and optional chaos fault injection."""
    original = getattr(target, method_name, None)
    if original is None:
        logger.debug(f"Cannot wrap {target}.{method_name}: method not found")
        return

    # Add chaos wrapper
    def chaos_wrapper(*args, **kwargs):
        chaos_cfg = AutoPatcher._global_chaos_config
        if chaos_cfg:
            error_rate = getattr(chaos_cfg, "chaos_error_rate", 0.0)
            delay_ms = getattr(chaos_cfg, "chaos_delay_ms", 0)
            
            # Inject delay
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
                
            # Inject error
            if error_rate > 0 and random.random() < error_rate:
                logger.warning(f"CHAOS ENGINEERING: Injecting synthetic fault into {method_name}")
                raise ChaosException(f"Synthetic Chaos fault injected in {method_name}")
                
        return wrapper(*args, **kwargs)

    async def async_chaos_wrapper(*args, **kwargs):
        chaos_cfg = AutoPatcher._global_chaos_config
        if chaos_cfg:
            error_rate = getattr(chaos_cfg, "chaos_error_rate", 0.0)
            delay_ms = getattr(chaos_cfg, "chaos_delay_ms", 0)
            
            # Inject delay
            if delay_ms > 0:
                await asyncio.sleep(delay_ms / 1000.0)
                
            # Inject error
            if error_rate > 0 and random.random() < error_rate:
                logger.warning(f"CHAOS ENGINEERING: Injecting synthetic fault into {method_name}")
                raise ChaosException(f"Synthetic Chaos fault injected in {method_name}")
                
        return await wrapper(*args, **kwargs)

    is_coroutine = asyncio.iscoroutinefunction(original) or asyncio.iscoroutinefunction(wrapper)
    final_wrapper = async_chaos_wrapper if is_coroutine else chaos_wrapper

    setattr(target, method_name, final_wrapper)
    logger.debug(f"Wrapped {target.__name__ if hasattr(target, '__name__') else target}.{method_name}")
