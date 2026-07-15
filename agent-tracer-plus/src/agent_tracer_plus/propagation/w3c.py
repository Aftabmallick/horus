"""W3C Trace Context propagation (traceparent + tracestate headers).

Implements injection into outgoing requests and extraction from incoming requests.
See: https://www.w3.org/TR/trace-context/
"""

from __future__ import annotations

import re
from typing import Dict, Optional

from agent_tracer_plus.core.context import get_current_span, get_current_trace
from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("propagation.w3c")

_TRACEPARENT_RE = re.compile(
    r"^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
)

class TraceContextData:
    """Parsed W3C Trace Context."""
    def __init__(self, trace_id: str, span_id: str, trace_flags: int = 1):
        self.trace_id = trace_id
        self.span_id = span_id
        self.trace_flags = trace_flags

class W3CTraceContextPropagator:
    """Injects/extracts W3C traceparent headers."""

    def inject(self, carrier: Dict[str, str]) -> Dict[str, str]:
        trace = get_current_trace()
        span = get_current_span()
        if trace and span:
            clean_trace_id = trace.trace_id.replace("-", "")[:32].ljust(32, "0")
            clean_span_id = span.span_id.replace("-", "")[:16].ljust(16, "0")
            traceparent = f"00-{clean_trace_id}-{clean_span_id}-01"
            carrier["traceparent"] = traceparent
        return carrier

    def extract(self, carrier: Dict[str, str]) -> Optional[TraceContextData]:
        traceparent = carrier.get("traceparent", "")
        if not traceparent:
            return None
        match = _TRACEPARENT_RE.match(traceparent.strip())
        if not match:
            logger.debug(f"Invalid traceparent: {traceparent}")
            return None
        _, trace_id, span_id, flags = match.groups()
        return TraceContextData(trace_id=trace_id, span_id=span_id, trace_flags=int(flags, 16))


# Module-level convenience functions
_propagator = W3CTraceContextPropagator()

def inject_context(headers: Dict[str, str]) -> Dict[str, str]:
    """Inject current trace context into headers dict."""
    return _propagator.inject(headers)

def extract_context(headers: Dict[str, str]) -> Optional[TraceContextData]:
    """Extract trace context from headers dict."""
    return _propagator.extract(headers)
