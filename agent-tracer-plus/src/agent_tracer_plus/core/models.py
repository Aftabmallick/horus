"""Core data models for Agent Tracer Plus.

Defines the trace/span/event hierarchy used throughout the library.
All models are plain dataclasses — no external dependencies required.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_tracer_plus.utils.clock import now_utc
from agent_tracer_plus.utils.ids import generate_execution_id, generate_span_id, generate_trace_id
from agent_tracer_plus.utils.serialization import safe_serialize

# ── Enums ──────────────────────────────────────────────────────────────────────


class SpanType(str, enum.Enum):
    """Type of work a span represents."""

    AGENT = "AGENT"
    LLM = "LLM"
    TOOL = "TOOL"
    RETRIEVAL = "RETRIEVAL"
    HANDOFF = "HANDOFF"
    RPC = "RPC"
    CHAIN = "CHAIN"
    GUARDRAIL = "GUARDRAIL"
    CUSTOM = "CUSTOM"
    MCP = "MCP"
    MEMORY = "MEMORY"
    WORKFLOW = "WORKFLOW"
    DATABASE = "DATABASE"
    EMBEDDING = "EMBEDDING"
    ROUTER = "ROUTER"
    EVALUATION = "EVALUATION"
    BROWSER = "BROWSER"
    POLICY = "POLICY"


class SpanStatus(str, enum.Enum):
    """Status of a span."""

    RUNNING = "RUNNING"
    OK = "OK"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class TraceStatus(str, enum.Enum):
    """Status of a trace."""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


# ── Token & Cost Tracking ──────────────────────────────────────────────────────


@dataclass
class TokenUsage:
    """Token usage for an LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0

    def __post_init__(self) -> None:
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens


@dataclass
class CostInfo:
    """Cost information for an LLM call."""

    input_cost: float = 0.0  # USD
    output_cost: float = 0.0  # USD
    total_cost: float = 0.0  # USD
    model: str = ""
    pricing_source: str = "auto"  # "auto" | "manual" | "custom"

    def __post_init__(self) -> None:
        if self.total_cost == 0.0:
            self.total_cost = self.input_cost + self.output_cost


# ── SpanLink ───────────────────────────────────────────────────────────────────


@dataclass
class SpanLink:
    """Link between spans across trace boundaries (for distributed tracing).

    Used to connect agent-to-agent handoffs, where the child may
    be in a different trace but causally related to this span.
    """

    linked_trace_id: str
    linked_span_id: str
    link_type: str = "child_of"  # "child_of" | "follows_from" | "caused_by"
    attributes: Dict[str, Any] = field(default_factory=dict)


# ── Event ──────────────────────────────────────────────────────────────────────


@dataclass
class Event:
    """A timestamped event within a span.

    Events represent discrete moments (checkpoints, state changes,
    guardrail triggers, etc.) rather than durations.
    """

    name: str
    timestamp: datetime = field(default_factory=now_utc)
    attributes: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=generate_span_id)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "event_id": self.event_id,
            "name": self.name,
            "timestamp": self.timestamp.isoformat(),
            "attributes": safe_serialize(self.attributes),
        }


# ── Span ───────────────────────────────────────────────────────────────────────


@dataclass
class Span:
    """A single unit of work within a trace.

    Spans form a tree: each span has an optional parent_span_id.
    The root span of a trace has parent_span_id = None.
    """

    name: str
    span_type: SpanType = SpanType.CUSTOM
    trace_id: str = ""
    span_id: str = field(default_factory=generate_span_id)
    parent_span_id: Optional[str] = None

    # Timing
    started_at: datetime = field(default_factory=now_utc)
    ended_at: Optional[datetime] = None
    duration_ms: float = 0.0

    # Internal timing (not serialized)
    _start_monotonic_ns: int = field(default=0, repr=False)

    # Status
    status: SpanStatus = SpanStatus.RUNNING

    # Data capture
    input: Optional[Any] = field(default=None, repr=False)
    output: Optional[Any] = field(default=None, repr=False)
    error: Optional[Dict[str, Any]] = field(default=None, repr=False)

    # Metadata
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Event] = field(default_factory=list)
    links: List[SpanLink] = field(default_factory=list)

    # LLM-specific
    token_usage: Optional[TokenUsage] = None
    cost_info: Optional[CostInfo] = None

    # Service info (for distributed tracing)
    service_name: str = ""
    service_instance_id: str = ""

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a custom attribute on this span."""
        self.attributes[key] = value

    def set_output(self, output: Any) -> None:
        """Set the output of this span."""
        self.output = output

    def set_error(self, error: BaseException) -> None:
        """Record an error on this span."""
        self.status = SpanStatus.ERROR
        self.error = {
            "type": type(error).__name__,
            "message": str(error),
            "module": type(error).__module__,
        }

    def add_event(self, name: str, attributes: Dict[str, Any] | None = None) -> Event:
        """Add a timestamped event to this span."""
        event = Event(name=name, attributes=attributes or {})
        self.events.append(event)
        return event

    def add_link(
        self,
        trace_id: str,
        span_id: str,
        link_type: str = "child_of",
        attributes: Dict[str, Any] | None = None,
    ) -> SpanLink:
        """Add a link to a span in another trace."""
        link = SpanLink(
            linked_trace_id=trace_id,
            linked_span_id=span_id,
            link_type=link_type,
            attributes=attributes or {},
        )
        self.links.append(link)
        return link

    def finish(self, status: SpanStatus | None = None) -> None:
        """Mark this span as finished."""
        from agent_tracer_plus.utils.clock import duration_ms as calc_duration
        from agent_tracer_plus.utils.clock import monotonic_ns

        self.ended_at = now_utc()
        if self._start_monotonic_ns > 0:
            self.duration_ms = calc_duration(self._start_monotonic_ns, monotonic_ns())
        if status is not None:
            self.status = status
        elif self.status == SpanStatus.RUNNING:
            self.status = SpanStatus.OK

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        result: Dict[str, Any] = {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "span_type": self.span_type.value if hasattr(self.span_type, "value") else self.span_type,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_ms": round(self.duration_ms, 3),
            "status": self.status.value if hasattr(self.status, "value") else self.status,
            "attributes": safe_serialize(self.attributes),
            "events": [e.to_dict() for e in self.events],
            "links": [
                {
                    "linked_trace_id": link.linked_trace_id,
                    "linked_span_id": link.linked_span_id,
                    "link_type": link.link_type,
                    "attributes": safe_serialize(link.attributes),
                }
                for link in self.links
            ],
            "service_name": self.service_name,
        }

        if self.input is not None:
            result["input"] = safe_serialize(self.input)
        if self.output is not None:
            result["output"] = safe_serialize(self.output)
        if self.error is not None:
            result["error"] = self.error
        if self.token_usage is not None:
            if isinstance(self.token_usage, dict):
                result["token_usage"] = self.token_usage
            else:
                result["token_usage"] = {
                    "input_tokens": getattr(self.token_usage, "input_tokens", 0),
                    "output_tokens": getattr(self.token_usage, "output_tokens", 0),
                    "total_tokens": getattr(self.token_usage, "total_tokens", 0),
                    "cached_tokens": getattr(self.token_usage, "cached_tokens", 0),
                }
        if self.cost_info is not None:
            if isinstance(self.cost_info, dict):
                result["cost_info"] = self.cost_info
            else:
                result["cost_info"] = {
                    "input_cost": getattr(self.cost_info, "input_cost", 0.0),
                    "output_cost": getattr(self.cost_info, "output_cost", 0.0),
                    "total_cost": getattr(self.cost_info, "total_cost", 0.0),
                    "model": getattr(self.cost_info, "model", ""),
                    "pricing_source": getattr(self.cost_info, "pricing_source", ""),
                }

        return result

    def to_otlp(self) -> Dict[str, Any]:
        """Serialize directly to OpenTelemetry Protobuf JSON mapping."""
        # Convert hex strings to byte-like representations (or keep as hex based on OTLP JSON spec)
        return {
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "parentSpanId": self.parent_span_id if self.parent_span_id else "",
            "name": self.name,
            "kind": 1,  # SPAN_KIND_INTERNAL
            "startTimeUnixNano": int(self.started_at.timestamp() * 1e9) if self.started_at else 0,
            "endTimeUnixNano": int(self.ended_at.timestamp() * 1e9) if self.ended_at else 0,
            "attributes": [{"key": k, "value": {"stringValue": str(v)}} for k, v in self.attributes.items()],
            "status": {"code": 1 if self.status == SpanStatus.OK else 2},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Span:
        """Deserialize from a dict."""
        span = cls(name=data.get("name") or data.get("trace_name") or "", span_id=data.get("span_id", ""))
        span.trace_id = data.get("trace_id", "")
        span.parent_span_id = data.get("parent_span_id") or data.get("parent_id")
        
        # Handle empty strings from protobuf
        if span.parent_span_id == "":
            span.parent_span_id = None

        try:
            span.span_type = SpanType(data.get("span_type", "CUSTOM"))
        except ValueError:
            span.span_type = SpanType.CUSTOM

        span.duration_ms = data.get("duration_ms", 0.0)
        try:
            span.status = SpanStatus(data.get("status", "RUNNING"))
        except ValueError:
            span.status = SpanStatus.RUNNING

        span.input = data.get("input")
        span.output = data.get("output")
        span.error = data.get("error") or data.get("error_message")
        span.attributes = data.get("attributes", {})
        span.service_name = data.get("service_name", "")

        start_time_val = data.get("started_at") or data.get("start_time")
        if start_time_val:
            try:
                span.started_at = datetime.fromisoformat(start_time_val.replace("Z", "+00:00"))
            except ValueError:
                pass

        end_time_val = data.get("ended_at") or data.get("end_time")
        if end_time_val:
            try:
                span.ended_at = datetime.fromisoformat(end_time_val.replace("Z", "+00:00"))
            except ValueError:
                pass

        # Calculate duration if missing
        if span.duration_ms == 0.0 and span.started_at and span.ended_at:
            span.duration_ms = (span.ended_at - span.started_at).total_seconds() * 1000

        return span
# ── Trace ──────────────────────────────────────────────────────────────────────


@dataclass
class Trace:
    """Top-level container representing an end-to-end agent execution.

    A trace contains one or more spans organized in a tree structure.
    The execution_id groups multiple traces from a single logical operation.
    """

    trace_id: str = field(default_factory=generate_trace_id)
    execution_id: str = field(default_factory=generate_execution_id)

    # Identity
    agent_name: str = ""
    service_name: str = ""
    session_id: str = ""
    tenant_id: str = ""

    # Timing
    started_at: datetime = field(default_factory=now_utc)
    ended_at: Optional[datetime] = None
    duration_ms: float = 0.0
    _start_monotonic_ns: int = field(default=0, repr=False)

    # Status
    status: TraceStatus = TraceStatus.RUNNING

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    # Spans (populated during execution)
    spans: List[Span] = field(default_factory=list, repr=False)

    # Aggregated metrics (computed on finish)
    total_tokens: int = 0
    total_cost: float = 0.0
    span_count: int = 0
    error_count: int = 0

    def set_metadata(self, data: Dict[str, Any]) -> None:
        """Merge metadata into the trace."""
        self.metadata.update(data)

    def add_tag(self, tag: str) -> None:
        """Add a tag to the trace."""
        if tag not in self.tags:
            self.tags.append(tag)

    def add_span(self, span: Span) -> None:
        """Register a span with this trace."""
        span.trace_id = self.trace_id
        span.service_name = self.service_name
        self.spans.append(span)

    def finish(self, status: TraceStatus | None = None) -> None:
        """Mark this trace as finished and compute aggregated metrics."""
        from agent_tracer_plus.utils.clock import duration_ms as calc_duration
        from agent_tracer_plus.utils.clock import monotonic_ns

        self.ended_at = now_utc()
        if self._start_monotonic_ns > 0:
            self.duration_ms = calc_duration(self._start_monotonic_ns, monotonic_ns())

        # Aggregate metrics from spans
        self.span_count = len(self.spans)
        self.error_count = sum(1 for s in self.spans if s.status == SpanStatus.ERROR)
        self.total_tokens = sum(
            (s.token_usage.get("total_tokens", 0) if isinstance(s.token_usage, dict) else getattr(s.token_usage, "total_tokens", 0))
            for s in self.spans if s.token_usage
        )
        self.total_cost = sum(
            (s.cost_info.get("total_cost", 0.0) if isinstance(s.cost_info, dict) else getattr(s.cost_info, "total_cost", 0.0))
            for s in self.spans if s.cost_info
        )

        if status is not None:
            self.status = status
        elif self.error_count > 0:
            self.status = TraceStatus.ERROR
        elif self.status == TraceStatus.RUNNING:
            self.status = TraceStatus.COMPLETED

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "trace_id": self.trace_id,
            "execution_id": self.execution_id,
            "agent_name": self.agent_name,
            "service_name": self.service_name,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_ms": round(self.duration_ms, 3),
            "status": self.status.value if hasattr(self.status, "value") else self.status,
            "metadata": safe_serialize(self.metadata),
            "tags": self.tags,
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 6),
            "span_count": self.span_count,
            "error_count": self.error_count,
        }

    def to_otlp(self) -> Dict[str, Any]:
        """Serialize directly to OpenTelemetry Protobuf ResourceSpans mapping."""
        return {
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": self.service_name}},
                    {"key": "agent.name", "value": {"stringValue": self.agent_name}},
                ]
            },
            "scopeSpans": [
                {
                    "scope": {"name": "agent-tracer-plus"},
                    "spans": [span.to_otlp() for span in self.spans]
                }
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Trace:
        """Deserialize from a dict."""
        trace = cls(trace_id=data.get("trace_id", ""))
        trace.execution_id = data.get("execution_id", "")
        trace.agent_name = data.get("agent_name", "")
        trace.service_name = data.get("service_name", "")
        trace.session_id = data.get("session_id", "")
        trace.tenant_id = data.get("tenant_id", "")
        trace.duration_ms = data.get("duration_ms", 0.0)
        trace.total_tokens = data.get("total_tokens", 0)
        trace.total_cost = data.get("total_cost", 0.0)
        trace.span_count = data.get("span_count", 0)
        trace.error_count = data.get("error_count", 0)
        trace.metadata = data.get("metadata", {})
        trace.tags = data.get("tags", [])

        try:
            trace.status = TraceStatus(data.get("status", "RUNNING"))
        except ValueError:
            trace.status = TraceStatus.RUNNING

        if "started_at" in data and data["started_at"]:
            try:
                trace.started_at = datetime.fromisoformat(data["started_at"])
            except ValueError:
                pass

        return trace
