"""Trace query filters for Agent Tracer Plus."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


@dataclass
class TraceFilter:
    """Structured filter for querying traces."""

    service_name: Optional[str] = None
    agent_name: Optional[str] = None
    status: Optional[str] = None
    min_duration_ms: Optional[float] = None
    max_duration_ms: Optional[float] = None
    min_cost: Optional[float] = None
    max_cost: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    tenant_id: Optional[str] = None
    session_id: Optional[str] = None
    time_range: Optional[str] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    has_errors: Optional[bool] = None
    min_tokens: Optional[int] = None
    max_tokens: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dict suitable for storage backends."""
        result: Dict[str, Any] = {}
        if self.service_name:
            result["service_name"] = self.service_name
        if self.agent_name:
            result["agent_name"] = self.agent_name
        if self.status:
            result["status"] = self.status
        if self.min_duration_ms is not None:
            result["min_duration_ms"] = self.min_duration_ms
        if self.max_duration_ms is not None:
            result["max_duration_ms"] = self.max_duration_ms
        if self.min_cost is not None:
            result["min_cost"] = self.min_cost
        if self.max_cost is not None:
            result["max_cost"] = self.max_cost
        if self.tags:
            result["tags"] = self.tags
        if self.tenant_id:
            result["tenant_id"] = self.tenant_id
        if self.session_id:
            result["session_id"] = self.session_id
        if self.has_errors is not None:
            result["has_errors"] = self.has_errors
        if self.since:
            result["since"] = self.since.isoformat()
        if self.until:
            result["until"] = self.until.isoformat()
        return result

    def apply_time_range(self) -> None:
        """Parse time_range string and set since/until."""
        if not self.time_range:
            return
        tr = self.time_range.strip()
        now = datetime.utcnow()
        if tr.startswith("last_") and tr.endswith("d"):
            try:
                days = int(tr[5:-1])
                self.since = now - timedelta(days=days)
            except ValueError:
                pass
        elif tr.startswith("last_") and tr.endswith("h"):
            try:
                hours = int(tr[5:-1])
                self.since = now - timedelta(hours=hours)
            except ValueError:
                pass

    def matches(self, trace_dict: Dict[str, Any]) -> bool:
        """Check if a trace dict matches this filter (client-side filtering)."""
        if self.service_name and trace_dict.get("service_name") != self.service_name:
            return False
        if self.agent_name and trace_dict.get("agent_name") != self.agent_name:
            return False
        if self.status and trace_dict.get("status") != self.status:
            return False
        if self.tenant_id and trace_dict.get("tenant_id") != self.tenant_id:
            return False
        if self.session_id and trace_dict.get("session_id") != self.session_id:
            return False
        if self.min_duration_ms is not None and trace_dict.get("duration_ms", 0) < self.min_duration_ms:
            return False
        if self.max_duration_ms is not None and trace_dict.get("duration_ms", 0) > self.max_duration_ms:
            return False
        if self.min_cost is not None and trace_dict.get("total_cost", 0) < self.min_cost:
            return False
        if self.max_cost is not None and trace_dict.get("total_cost", 0) > self.max_cost:
            return False
        if self.has_errors is True and trace_dict.get("error_count", 0) == 0:
            return False
        if self.has_errors is False and trace_dict.get("error_count", 0) > 0:
            return False
        if self.tags:
            trace_tags = trace_dict.get("tags", [])
            if not all(t in trace_tags for t in self.tags):
                return False
        return True


def build_filter(**kwargs: Any) -> TraceFilter:
    """Build a TraceFilter from keyword arguments."""
    f = TraceFilter()
    for key, value in kwargs.items():
        if hasattr(f, key) and value is not None:
            setattr(f, key, value)
    f.apply_time_range()
    return f
