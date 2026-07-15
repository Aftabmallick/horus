"""Trace analytics — aggregation and reporting over trace data."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from agent_tracer_plus.core.context import get_tracer
from agent_tracer_plus.query.filters import TraceFilter

logger = logging.getLogger(__name__)


class TraceAnalytics:
    """Compute analytics over stored traces."""

    def __init__(self, time_range: str = "last_7d"):
        self.time_range = time_range

    async def _fetch_traces(self, extra_filter: Optional[TraceFilter] = None) -> List[Dict[str, Any]]:
        tracer = get_tracer()
        if not tracer:
            return []
        traces = await tracer.query(limit=10000)
        if extra_filter:
            traces = [t for t in traces if extra_filter.matches(t)]
        return traces

    async def summary(self) -> Dict[str, Any]:
        """High-level summary of traces in the time range."""
        traces = await self._fetch_traces()
        if not traces:
            return {"total_traces": 0}

        total = len(traces)
        errors = sum(1 for t in traces if t.get("status") == "ERROR")
        total_cost = sum(t.get("total_cost", 0) for t in traces)
        total_tokens = sum(t.get("total_tokens", 0) for t in traces)
        durations = [t.get("duration_ms", 0) for t in traces]
        avg_duration = sum(durations) / total if total else 0

        return {
            "total_traces": total,
            "error_count": errors,
            "error_rate": round(errors / total * 100, 2) if total else 0,
            "total_cost_usd": round(total_cost, 4),
            "total_tokens": total_tokens,
            "avg_duration_ms": round(avg_duration, 2),
            "p50_duration_ms": round(sorted(durations)[total // 2], 2) if durations else 0,
            "p99_duration_ms": round(sorted(durations)[int(total * 0.99)], 2) if total > 1 else 0,
        }

    async def cost_by_model(self) -> Dict[str, float]:
        """Break down costs by model."""
        tracer = get_tracer()
        if not tracer:
            return {}

        traces = await self._fetch_traces()
        model_costs: Dict[str, float] = defaultdict(float)
        for t in traces:
            trace_id = t.get("trace_id", "")
            if not trace_id:
                continue
            spans = await tracer.get_spans(trace_id)
            for s in spans:
                if s.cost_info:
                    ci = s.cost_info
                    model = ci.get("model", "unknown") if isinstance(ci, dict) else getattr(ci, "model", "unknown")
                    cost = ci.get("total_cost", 0) if isinstance(ci, dict) else getattr(ci, "total_cost", 0)
                    model_costs[model] += cost

        return dict(model_costs)

    async def cost_by_agent(self) -> Dict[str, float]:
        """Break down costs by agent name."""
        traces = await self._fetch_traces()
        agent_costs: Dict[str, float] = defaultdict(float)
        for t in traces:
            agent = t.get("agent_name", "unknown")
            agent_costs[agent] += t.get("total_cost", 0)
        return dict(agent_costs)

    async def error_breakdown(self) -> Dict[str, int]:
        """Break down errors by type."""
        tracer = get_tracer()
        if not tracer:
            return {}

        traces = await self._fetch_traces()
        error_types: Dict[str, int] = defaultdict(int)
        for t in traces:
            if t.get("status") != "ERROR":
                continue
            trace_id = t.get("trace_id", "")
            if not trace_id:
                continue
            spans = await tracer.get_spans(trace_id)
            for s in spans:
                if s.error:
                    err_type = s.error.get("type", "Unknown") if isinstance(s.error, dict) else "Unknown"
                    error_types[err_type] += 1

        return dict(error_types)

    async def throughput(self) -> Dict[str, Any]:
        """Calculate throughput metrics."""
        traces = await self._fetch_traces()
        if not traces:
            return {"traces_per_minute": 0}

        durations = [t.get("duration_ms", 0) for t in traces]
        return {
            "total_traces": len(traces),
            "avg_duration_ms": round(sum(durations) / len(durations), 2),
            "traces_per_minute": round(len(traces) / max(1, sum(durations) / 60000), 2),
        }
