"""Base classes for plugins."""

import logging
from abc import ABC
from typing import Any, Dict, List

from agent_tracer_plus.core.models import Trace, Span

logger = logging.getLogger(__name__)


class PluginBase(ABC):
    """Base class for all community plugins."""

    name: str = "base"
    version: str = "0.1.0"

    def setup(self, config: Dict[str, Any]) -> None:
        """Initialize plugin."""
        pass

    def on_start(self, tracer: Any) -> None:
        """Called when the tracer starts."""
        pass

    def on_span_start(self, span: Span) -> None:
        """Called when a span starts. 
        Note: This is synchronous, keep it fast!
        """
        pass

    def on_span_end(self, span: Span) -> None:
        """Called when a span ends."""
        pass

    def on_trace_end(self, trace: Trace) -> None:
        """Called when a trace is completed and enqueued."""
        pass

    def on_shutdown(self) -> None:
        """Called when the tracer is shutting down."""
        pass


class InstrumentorPlugin(PluginBase):
    """Base class for auto-instrumentation plugins."""

    target_modules: List[str] = []

    def patch(self) -> None:
        """Apply monkey-patches."""
        pass


class ExporterPlugin(PluginBase):
    """Base class for export format plugins."""

    format_name: str = ""

    def export(self, traces: List[Trace], output_path: str) -> None:
        """Export traces."""
        pass

