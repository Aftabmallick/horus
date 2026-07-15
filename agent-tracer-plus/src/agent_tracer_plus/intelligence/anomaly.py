"""Anomaly detection using EWMA (Exponentially Weighted Moving Average) for online detection."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("intelligence.anomaly")


@dataclass
class AnomalyAlert:
    """Anomalous behavior detected in a trace."""
    anomaly_type: str
    severity: str  # "LOW", "MEDIUM", "HIGH"
    message: str
    details: Dict[str, Any]


class AnomalyDetector:
    """Online anomaly detector.
    
    Evaluates traces immediately as they finish for:
    - Infinite loops (repeated identical tool calls)
    - High latency outliers (via EWMA)
    - Error floods
    """

    def __init__(self, ewma_alpha: float = 0.2, latency_threshold_stddev: float = 3.0) -> None:
        self.ewma_alpha = ewma_alpha
        self.latency_threshold_stddev = latency_threshold_stddev
        
        # Internal state for EWMA tracking
        # We track latency by agent_name
        self._ewma_latency: Dict[str, float] = {}
        self._ewma_variance: Dict[str, float] = {}

    def detect_trace_anomalies(self, trace: Trace) -> List[AnomalyAlert]:
        """Run all online detection rules against a newly completed trace."""
        alerts = []
        
        # 1. Detect tool loops
        loop_alert = self._detect_loops(trace.spans)
        if loop_alert:
            alerts.append(loop_alert)
            
        # 2. Detect latency outliers (update EWMA)
        latency_alert = self._update_and_check_latency(trace)
        if latency_alert:
            alerts.append(latency_alert)
            
        # 3. Detect excessive tool calls
        count_alert = self._detect_excessive_tools(trace.spans)
        if count_alert:
            alerts.append(count_alert)
            
        if alerts:
            logger.warning(
                f"Detected {len(alerts)} anomalies in trace {trace.trace_id} "
                f"({', '.join(a.anomaly_type for a in alerts)})"
            )
            
        return alerts

    def _detect_loops(self, spans: List[Span]) -> Optional[AnomalyAlert]:
        """Detect if an agent is stuck calling the same tool repeatedly."""
        tool_spans = [
            s for s in spans 
            if (s.span_type.value.upper() if hasattr(s.span_type, 'value') else str(s.span_type).upper()) == "TOOL"
        ]
        if len(tool_spans) < 3:
            return None
            
        # Look for 3 consecutive identical tool calls (same tool, same input)
        for i in range(len(tool_spans) - 2):
            s1, s2, s3 = tool_spans[i], tool_spans[i+1], tool_spans[i+2]
            
            # Simple check: same name and same input
            if s1.name == s2.name == s3.name:
                if str(s1.input) == str(s2.input) == str(s3.input):
                    return AnomalyAlert(
                        anomaly_type="infinite_loop",
                        severity="HIGH",
                        message=f"Agent seems stuck in a loop calling '{s1.name}' with identical inputs.",
                        details={
                            "tool_name": s1.name,
                            "repeated_count": 3,
                            "span_ids": [s1.span_id, s2.span_id, s3.span_id]
                        }
                    )
        return None

    def _update_and_check_latency(self, trace: Trace) -> Optional[AnomalyAlert]:
        """Update EWMA stats and check if this trace is a latency outlier."""
        if not trace.started_at or not trace.ended_at:
            return None
            
        latency_ms = (trace.ended_at - trace.started_at) * 1000
        agent = trace.agent_name or "unknown"
        
        # Initialize if new
        if agent not in self._ewma_latency:
            self._ewma_latency[agent] = latency_ms
            self._ewma_variance[agent] = 0.0
            return None
            
        # Calculate deviation before updating stats
        current_mean = self._ewma_latency[agent]
        current_var = self._ewma_variance[agent]
        current_stddev = current_var ** 0.5
        
        alert = None
        
        # If we have enough variance history to compare
        if current_stddev > 10.0:  # Ignore micro-variations
            deviation = abs(latency_ms - current_mean)
            if deviation > (self.latency_threshold_stddev * current_stddev):
                severity = "HIGH" if deviation > (5.0 * current_stddev) else "MEDIUM"
                alert = AnomalyAlert(
                    anomaly_type="latency_spike",
                    severity=severity,
                    message=f"Trace latency ({latency_ms:.0f}ms) is unusually high for agent '{agent}'.",
                    details={
                        "latency_ms": latency_ms,
                        "ewma_mean_ms": current_mean,
                        "ewma_stddev_ms": current_stddev,
                        "deviation_sigma": deviation / current_stddev
                    }
                )
                
        # Update EWMA stats (using incremental variance calculation)
        diff = latency_ms - current_mean
        incr = self.ewma_alpha * diff
        self._ewma_latency[agent] = current_mean + incr
        self._ewma_variance[agent] = (1 - self.ewma_alpha) * (self._ewma_variance[agent] + diff * incr)
        
        return alert

    def _detect_excessive_tools(self, spans: List[Span]) -> Optional[AnomalyAlert]:
        """Detect unusually high number of tool calls (potential runaway agent)."""
        tool_count = sum(
            1 for s in spans 
            if (s.span_type.value.upper() if hasattr(s.span_type, 'value') else str(s.span_type).upper()) == "TOOL"
        )
        
        if tool_count > 15:
            return AnomalyAlert(
                anomaly_type="excessive_tool_usage",
                severity="HIGH" if tool_count > 30 else "MEDIUM",
                message=f"Agent made an unusually high number of tool calls ({tool_count}).",
                details={"tool_call_count": tool_count}
            )
        return None
