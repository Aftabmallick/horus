"""Plugin loader using entry points."""

import logging
import asyncio
import concurrent.futures
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Handle importlib.metadata for Python < 3.8 if needed,
# but Python 3.8+ is assumed.
from importlib.metadata import entry_points


class PluginLoader:
    """Loads plugins via entry points and manages their lifecycle."""

    def __init__(self, group_name: str = "agent_tracer_plus.plugins"):
        self.group_name = group_name
        self.plugins = {}
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

    def discover_and_load(self, config: Dict[str, Any]) -> None:
        """Discover and load all registered plugins."""
        try:
            # Python 3.10+ style
            eps = entry_points(group=self.group_name)
        except TypeError:
            # Python 3.8/3.9 style
            eps = entry_points().get(self.group_name, [])

        for ep in eps:
            try:
                plugin_cls = ep.load()
                plugin = plugin_cls()
                
                # Sandbox plugin setup with a strict 5-second timeout
                future = self._executor.submit(plugin.setup, config)
                future.result(timeout=5.0)
                
                self.plugins[plugin.name] = plugin
                logger.info(f"Loaded plugin '{plugin.name}' (v{getattr(plugin, 'version', 'unknown')})")
            except concurrent.futures.TimeoutError:
                logger.error(f"Plugin {ep.name} timed out during setup and was sandboxed/disabled.")
            except Exception as e:
                logger.error(f"Failed to load plugin from {ep.name}: {e}")

    def get_plugin(self, name: str):
        """Get a loaded plugin by name."""
        return self.plugins.get(name)

    def trigger_on_start(self, tracer: Any) -> None:
        """Trigger on_start for all plugins."""
        for plugin in self.plugins.values():
            if hasattr(plugin, "on_start"):
                try:
                    plugin.on_start(tracer)
                except Exception as e:
                    logger.error(f"Plugin {plugin.name} failed on_start: {e}")

    def trigger_on_span_start(self, span: Any) -> None:
        """Trigger on_span_start synchronously (must be fast)."""
        for plugin in self.plugins.values():
            if hasattr(plugin, "on_span_start"):
                try:
                    plugin.on_span_start(span)
                except Exception as e:
                    logger.error(f"Plugin {plugin.name} failed on_span_start: {e}")

    def trigger_on_span_end(self, span: Any) -> None:
        """Trigger on_span_end in background threads."""
        for plugin in self.plugins.values():
            if hasattr(plugin, "on_span_end"):
                self._executor.submit(self._safe_call, plugin.name, plugin.on_span_end, span)

    def trigger_on_trace_end(self, trace: Any) -> None:
        """Trigger on_trace_end in background threads."""
        for plugin in self.plugins.values():
            if hasattr(plugin, "on_trace_end"):
                self._executor.submit(self._safe_call, plugin.name, plugin.on_trace_end, trace)

    def trigger_on_shutdown(self) -> None:
        """Trigger on_shutdown and cleanup."""
        for plugin in self.plugins.values():
            if hasattr(plugin, "on_shutdown"):
                try:
                    plugin.on_shutdown()
                except Exception as e:
                    logger.error(f"Plugin {plugin.name} failed on_shutdown: {e}")
        self._executor.shutdown(wait=False)

    def _safe_call(self, plugin_name: str, func, *args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Plugin {plugin_name} background task failed: {e}")

