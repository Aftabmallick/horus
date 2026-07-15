"""B3 (Zipkin) trace context propagation.

Supports both single-header and multi-header B3 formats.
See: https://github.com/openzipkin/b3-propagation
"""

from __future__ import annotations

from typing import Dict, Optional

from agent_tracer_plus.core.context import get_current_span, get_current_trace
from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("propagation.b3")


class B3TraceContextData:
    """Parsed B3 trace context."""

    def __init__(self, trace_id: str, span_id: str, sampled: bool = True, parent_span_id: Optional[str] = None):
        self.trace_id = trace_id
        self.span_id = span_id
        self.sampled = sampled
        self.parent_span_id = parent_span_id


class B3Propagator:
    """Injects/extracts B3 (Zipkin) trace context headers.

    Supports:
      - Single header: b3: {trace_id}-{span_id}-{sampling}-{parent_span_id}
      - Multi-header: X-B3-TraceId, X-B3-SpanId, X-B3-Sampled, X-B3-ParentSpanId
    """

    # ── Injection ──

    def inject(self, carrier: Dict[str, str], single_header: bool = False) -> Dict[str, str]:
        """Inject current trace context into carrier headers."""
        trace = get_current_trace()
        span = get_current_span()
        if not trace or not span:
            return carrier

        trace_id = trace.trace_id[:32].ljust(32, "0")
        span_id = span.span_id[:16].ljust(16, "0")
        parent_id = span.parent_span_id[:16].ljust(16, "0") if span.parent_span_id else None
        sampled = "1"

        if single_header:
            # Single-header format: {TraceId}-{SpanId}-{Sampling}-{ParentSpanId}
            parts = [trace_id, span_id, sampled]
            if parent_id:
                parts.append(parent_id)
            carrier["b3"] = "-".join(parts)
        else:
            # Multi-header format
            carrier["X-B3-TraceId"] = trace_id
            carrier["X-B3-SpanId"] = span_id
            carrier["X-B3-Sampled"] = sampled
            if parent_id:
                carrier["X-B3-ParentSpanId"] = parent_id

        return carrier

    # ── Extraction ──

    def extract(self, carrier: Dict[str, str]) -> Optional[B3TraceContextData]:
        """Extract B3 trace context from carrier headers."""
        # Try single header first
        b3_single = carrier.get("b3", "")
        if b3_single:
            return self._parse_single(b3_single)

        # Multi-header
        trace_id = carrier.get("X-B3-TraceId", "")
        span_id = carrier.get("X-B3-SpanId", "")
        if not trace_id or not span_id:
            return None

        sampled = carrier.get("X-B3-Sampled", "1") == "1"
        parent_id = carrier.get("X-B3-ParentSpanId")

        return B3TraceContextData(
            trace_id=trace_id,
            span_id=span_id,
            sampled=sampled,
            parent_span_id=parent_id,
        )

    def _parse_single(self, value: str) -> Optional[B3TraceContextData]:
        """Parse B3 single-header format."""
        # Handle deny/accept shorthand
        if value == "0":
            return B3TraceContextData(trace_id="", span_id="", sampled=False)
        if value == "1" or value == "d":
            return None  # Accept but no context to extract

        parts = value.split("-")
        if len(parts) < 2:
            logger.debug(f"Invalid b3 single header: {value}")
            return None

        trace_id = parts[0]
        span_id = parts[1]
        sampled = parts[2] == "1" if len(parts) > 2 else True
        parent_id = parts[3] if len(parts) > 3 else None

        return B3TraceContextData(
            trace_id=trace_id,
            span_id=span_id,
            sampled=sampled,
            parent_span_id=parent_id,
        )


# Module-level convenience
_propagator = B3Propagator()


def inject_b3(headers: Dict[str, str], single_header: bool = False) -> Dict[str, str]:
    """Inject B3 trace context into headers."""
    return _propagator.inject(headers, single_header=single_header)


def extract_b3(headers: Dict[str, str]) -> Optional[B3TraceContextData]:
    """Extract B3 trace context from headers."""
    return _propagator.extract(headers)
