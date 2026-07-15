"""SLA Monitoring."""

import logging
import collections
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class SLAMonitor:
    """Monitors trace metrics against SLA definitions using sliding windows and error budgets."""

    def __init__(self, window_size: int = 1000):
        self.slas: List[Dict[str, Any]] = []
        self.window_size = window_size
        self._history: Dict[str, collections.deque] = collections.defaultdict(
            lambda: collections.deque(maxlen=window_size)
        )
        self._error_budgets: Dict[str, float] = {} # Tracks remaining budget (e.g. 100.0)

    def add_sla(self, agent: str, metric: str, threshold: float, error_budget: float = 100.0):
        sla_id = f"{agent}:{metric}"
        self.slas.append({"id": sla_id, "agent": agent, "metric": metric, "threshold": threshold})
        if sla_id not in self._error_budgets:
            self._error_budgets[sla_id] = error_budget

    def _calculate_percentile(self, values: List[float], percentile: float) -> float:
        if not values:
            return 0.0
        sorted_values = sorted(values)
        k = (len(sorted_values) - 1) * percentile
        f = int(k)
        c = int(k) + 1 if int(k) + 1 < len(sorted_values) else int(k)
        if f == c:
            return sorted_values[f]
        d0 = sorted_values[f] * (c - k)
        d1 = sorted_values[c] * (k - f)
        return d0 + d1

    async def check_compliance(self, stats: Dict[str, Any]) -> bool:
        """Check if current stats meet SLAs, update sliding windows, and burn error budgets."""
        compliance = True
        for sla in self.slas:
            sla_id = sla["id"]
            agent = sla["agent"]
            metric = sla["metric"]
            threshold = sla["threshold"]

            # Extract agent specific stats if nested, or use global stats if agent is "*"
            agent_stats = stats.get(agent, stats) if agent != "*" else stats

            if metric not in agent_stats:
                logger.debug(f"Metric {metric} not found in stats for agent {agent}. Skipping SLA check.")
                continue

            value = agent_stats[metric]
            
            # Store in sliding window for percentiles if metric is a numeric value
            if isinstance(value, (int, float)):
                self._history[sla_id].append(value)
                
            # If metric requests a percentile (e.g. p95_latency)
            eval_value = value
            if metric.startswith("p") and "_" in metric:
                try:
                    p_val = float(metric.split("_")[0][1:]) / 100.0
                    history_vals = list(self._history[sla_id])
                    eval_value = self._calculate_percentile(history_vals, p_val)
                except Exception:
                    pass

            # Logic: success rates (higher is better). Errors/latency (lower is better).
            if "success" in metric.lower():
                passed = eval_value >= threshold
            else:
                passed = eval_value <= threshold

            if not passed:
                # Burn Error Budget
                burn_amount = abs(eval_value - threshold)
                self._error_budgets[sla_id] -= burn_amount
                
                logger.warning(
                    f"SLA Breach for {agent}: {metric} = {eval_value} (Threshold: {threshold}). "
                    f"Remaining Error Budget: {self._error_budgets[sla_id]:.2f}"
                )
                
                if self._error_budgets[sla_id] <= 0:
                    logger.error(f"ERROR BUDGET EXHAUSTED FOR {sla_id}!")
                
                compliance = False
            else:
                logger.debug(f"SLA Met for {agent}: {metric} = {eval_value}")

        return compliance
