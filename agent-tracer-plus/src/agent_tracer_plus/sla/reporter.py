"""SLA compliance reporting."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from agent_tracer_plus.core.context import get_tracer

logger = logging.getLogger(__name__)


class SLAReporter:
    """Generate SLA compliance reports from trace data."""

    def __init__(self, slas: Optional[List[Dict[str, Any]]] = None) -> None:
        self.slas = slas or []

    async def generate_report(self, time_range: str = "last_7d") -> Dict[str, Any]:
        """Generate a comprehensive SLA compliance report.

        Returns:
            Dict with compliance summary, per-SLA results, breach history.
        """
        tracer = get_tracer()
        if not tracer:
            return {"error": "Tracer not initialized"}

        traces = await tracer.query(limit=10000)
        if not traces:
            return {"status": "no_data", "slas": []}

        # Parse time range
        days = 7
        if time_range.startswith("last_") and time_range.endswith("d"):
            try:
                days = int(time_range[5:-1])
            except ValueError:
                pass

        # Compute per-agent stats
        agent_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total": 0,
            "errors": 0,
            "durations": [],
            "costs": [],
        })

        for t in traces:
            agent = t.get("agent_name", "*")
            stats = agent_stats[agent]
            stats["total"] += 1
            if t.get("status") == "ERROR":
                stats["errors"] += 1
            stats["durations"].append(t.get("duration_ms", 0))
            stats["costs"].append(t.get("total_cost", 0))

        # Also compute global stats
        all_durations = [t.get("duration_ms", 0) for t in traces]
        all_errors = sum(1 for t in traces if t.get("status") == "ERROR")
        agent_stats["*"] = {
            "total": len(traces),
            "errors": all_errors,
            "durations": all_durations,
            "costs": [t.get("total_cost", 0) for t in traces],
        }

        # Evaluate each SLA
        sla_results = []
        total_breaches = 0

        for sla in self.slas:
            agent = sla.get("agent", "*")
            metric = sla.get("metric", "")
            threshold = sla.get("threshold", 0)

            stats = agent_stats.get(agent, agent_stats.get("*", {}))
            if not stats or stats.get("total", 0) == 0:
                sla_results.append({
                    "sla": sla,
                    "status": "no_data",
                    "actual": None,
                    "compliant": True,
                })
                continue

            # Calculate actual metric value
            actual = self._calculate_metric(metric, stats)
            compliant = self._check_compliance(metric, actual, threshold)

            if not compliant:
                total_breaches += 1

            sla_results.append({
                "sla": sla,
                "actual": round(actual, 4) if actual is not None else None,
                "threshold": threshold,
                "compliant": compliant,
                "status": "compliant" if compliant else "breached",
            })

        total_slas = len(self.slas)
        compliance_rate = ((total_slas - total_breaches) / total_slas * 100) if total_slas > 0 else 100

        return {
            "time_range": time_range,
            "total_traces": len(traces),
            "total_slas": total_slas,
            "breaches": total_breaches,
            "compliance_rate": round(compliance_rate, 2),
            "sla_results": sla_results,
        }

    def _calculate_metric(self, metric: str, stats: Dict[str, Any]) -> Optional[float]:
        """Calculate the actual value for a metric."""
        total = stats.get("total", 0)
        if total == 0:
            return None

        if metric == "success_rate":
            errors = stats.get("errors", 0)
            return (total - errors) / total * 100
        elif metric == "error_rate":
            return stats.get("errors", 0) / total * 100
        elif metric == "p99_latency":
            durations = sorted(stats.get("durations", []))
            idx = int(len(durations) * 0.99)
            return durations[min(idx, len(durations) - 1)] if durations else 0
        elif metric == "p95_latency":
            durations = sorted(stats.get("durations", []))
            idx = int(len(durations) * 0.95)
            return durations[min(idx, len(durations) - 1)] if durations else 0
        elif metric == "avg_latency":
            durations = stats.get("durations", [])
            return sum(durations) / len(durations) if durations else 0
        elif metric == "total_cost":
            return sum(stats.get("costs", []))
        return None

    def _check_compliance(self, metric: str, actual: Optional[float], threshold: float) -> bool:
        """Check if a metric value meets the SLA threshold."""
        if actual is None:
            return True  # No data = compliant by default
        # Success rates: higher is better
        if "success" in metric.lower():
            return actual >= threshold
        # Everything else: lower is better
        return actual <= threshold


async def generate_sla_report(
    slas: Optional[List[Dict[str, Any]]] = None,
    time_range: str = "last_7d",
) -> Dict[str, Any]:
    """Generate SLA compliance report. Convenience wrapper."""
    reporter = SLAReporter(slas=slas or [])
    return await reporter.generate_report(time_range=time_range)
