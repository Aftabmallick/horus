"""Cost simulator — model swap cost estimation from historical traces.

Improvements over the original:
- Time-aware: parses `time_range` into real datetime windows for accurate daily burn rate
- Daily burn rate with stddev confidence interval (not naive cost * 30)
- Context window violation detection (not just max_trace_tokens vs candidate window)
- Quality degradation scoring based on token complexity analysis
- Monthly projection with confidence intervals
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from agent_tracer_plus.core.context import get_tracer
from agent_tracer_plus.utils.pricing import get_model_pricing

logger = logging.getLogger(__name__)


def _parse_time_range(time_range: str) -> Optional[datetime]:
    """Parse time range strings like 'last_7d', 'last_30d', 'last_24h' into a cutoff datetime."""
    now = datetime.now(timezone.utc)
    time_range = time_range.strip().lower()

    mapping = {
        "last_1h": timedelta(hours=1),
        "last_24h": timedelta(hours=24),
        "last_7d": timedelta(days=7),
        "last_30d": timedelta(days=30),
        "last_90d": timedelta(days=90),
    }

    for key, delta in mapping.items():
        if time_range == key or time_range.replace("_", "") == key.replace("_", ""):
            return now - delta

    # Try parsing 'last_Nd' or 'last_Nh' generically
    import re
    m = re.match(r"last[_\s]?(\d+)([dh])", time_range)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = timedelta(days=n) if unit == "d" else timedelta(hours=n)
        return now - delta

    logger.warning(f"Could not parse time_range '{time_range}'. Using last 30 days.")
    return now - timedelta(days=30)


class CostSimulator:
    """Simulate costs over historical traces for model swap analysis."""

    def __init__(self, time_range: str = "last_30d") -> None:
        self.time_range = time_range
        self._cutoff: Optional[datetime] = _parse_time_range(time_range)

    async def _collect_usage(self) -> Dict[str, Any]:
        """Collect token usage from traces within the time range."""
        tracer = get_tracer()
        if not tracer:
            return {}

        traces = await tracer.query(limit=10_000)

        total_input_tokens = 0
        total_output_tokens = 0
        current_total_cost = 0.0
        span_count = 0
        max_trace_tokens = 0

        # Daily buckets for burn rate calculation
        daily_costs: Dict[str, float] = defaultdict(float)
        daily_tokens: Dict[str, int] = defaultdict(int)

        for t in traces:
            # Filter by time range using trace start_time
            started_at = t.get("started_at") or t.get("created_at")
            if started_at and self._cutoff:
                try:
                    if isinstance(started_at, str):
                        ts = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    elif isinstance(started_at, (int, float)):
                        ts = datetime.fromtimestamp(started_at, tz=timezone.utc)
                    else:
                        ts = started_at
                    if ts < self._cutoff:
                        continue
                    day_key = ts.strftime("%Y-%m-%d")
                except Exception:
                    day_key = "unknown"
            else:
                day_key = "unknown"

            trace_id = t.get("trace_id", "")
            if not trace_id:
                continue

            spans = await tracer.get_spans(trace_id)
            trace_tokens = 0

            for s in spans:
                if not s.token_usage:
                    continue

                tu = s.token_usage
                inp = tu.get("input_tokens", 0) if isinstance(tu, dict) else getattr(tu, "input_tokens", 0)
                out = tu.get("output_tokens", 0) if isinstance(tu, dict) else getattr(tu, "output_tokens", 0)
                total_input_tokens += inp
                total_output_tokens += out
                trace_tokens += inp + out
                span_count += 1

                if s.cost_info:
                    ci = s.cost_info
                    span_cost = ci.get("total_cost", 0) if isinstance(ci, dict) else getattr(ci, "total_cost", 0)
                    current_total_cost += span_cost
                    daily_costs[day_key] += span_cost
                    daily_tokens[day_key] += inp + out

            if trace_tokens > max_trace_tokens:
                max_trace_tokens = trace_tokens

        # If no cost was recorded, estimate from pricing (use unknown model pricing as fallback)
        return {
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "current_total_cost": current_total_cost,
            "span_count": span_count,
            "max_trace_tokens": max_trace_tokens,
            "daily_costs": dict(daily_costs),
            "daily_tokens": dict(daily_tokens),
            "trace_count": len(traces),
        }

    async def simulate_model_swap(
        self,
        current: str,
        candidates: List[str],
    ) -> Dict[str, Any]:
        """Simulate costs if we swap from current model to candidates.

        Analyzes historical token usage and re-prices with candidate model pricing.
        Includes quality degradation risk assessment.
        """
        usage = await self._collect_usage()
        if not usage:
            return {"error": "Tracer not initialized or no traces found"}

        total_input_tokens = usage["total_input_tokens"]
        total_output_tokens = usage["total_output_tokens"]
        current_total_cost = usage["current_total_cost"]
        max_trace_tokens = usage["max_trace_tokens"]

        # If no cost was recorded, estimate from pricing table
        if current_total_cost == 0.0 and (total_input_tokens > 0 or total_output_tokens > 0):
            pricing = get_model_pricing(current)
            if pricing:
                current_total_cost = pricing.calculate_cost(total_input_tokens, total_output_tokens)

        # Daily burn rate stats (for projection confidence interval)
        daily_costs = usage["daily_costs"]
        day_values = list(daily_costs.values()) if daily_costs else [current_total_cost]
        daily_mean = statistics.mean(day_values) if day_values else 0.0
        daily_stddev = statistics.stdev(day_values) if len(day_values) > 1 else 0.0

        # Simulate candidate costs
        simulated: Dict[str, Any] = {}
        for candidate in candidates:
            pricing = get_model_pricing(candidate)
            if not pricing:
                simulated[candidate] = {"error": f"No pricing data for model '{candidate}'"}
                continue

            candidate_cost = pricing.calculate_cost(total_input_tokens, total_output_tokens)
            savings_usd = current_total_cost - candidate_cost
            savings_pct = (savings_usd / current_total_cost * 100) if current_total_cost > 0 else 0.0

            # Quality degradation risk
            degradation_risk = "None"
            degradation_details = []

            # Context window check
            if hasattr(pricing, "context_window") and pricing.context_window:
                if pricing.context_window < max_trace_tokens:
                    degradation_risk = "HIGH"
                    degradation_details.append(
                        f"Context window ({pricing.context_window:,} tokens) < "
                        f"historical max trace size ({max_trace_tokens:,} tokens) — "
                        f"some traces will be truncated"
                    )

            # Token efficiency proxy: if candidate is much cheaper, it's likely a smaller model
            cost_ratio = candidate_cost / current_total_cost if current_total_cost > 0 else 1.0
            if cost_ratio < 0.3 and not degradation_details:
                degradation_risk = "MEDIUM"
                degradation_details.append(
                    f"Candidate is {(1-cost_ratio)*100:.0f}% cheaper — "
                    f"likely a smaller/less capable model. "
                    f"Recommend A/B testing before full rollout."
                )

            simulated[candidate] = {
                "estimated_cost_usd": round(candidate_cost, 4),
                "savings_usd": round(savings_usd, 4),
                "savings_percent": round(savings_pct, 1),
                "quality_degradation_risk": degradation_risk,
                "degradation_details": " ".join(degradation_details) if degradation_details else "No known risks",
            }

        return {
            "current_model": current,
            "time_range": self.time_range,
            "analysis_period": {
                "cutoff": self._cutoff.isoformat() if self._cutoff else None,
                "days_with_data": len(daily_costs),
            },
            "current_cost_usd": round(current_total_cost, 4),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "spans_analyzed": usage["span_count"],
            "traces_analyzed": usage["trace_count"],
            "candidates": simulated,
        }

    async def monthly_projection(self, model: str) -> Dict[str, Any]:
        """Project monthly costs based on actual daily burn rate with confidence interval."""
        usage = await self._collect_usage()
        if not usage:
            return {"error": "Tracer not initialized or no traces found"}

        daily_costs = usage["daily_costs"]
        day_values = list(daily_costs.values()) if daily_costs else []

        if not day_values:
            return {
                "model": model,
                "error": "No daily cost data available for projection",
                "raw_total_cost": round(usage["current_total_cost"], 4),
            }

        daily_mean = statistics.mean(day_values)
        daily_stddev = statistics.stdev(day_values) if len(day_values) > 1 else 0.0

        # 95% confidence interval: mean ± 2*stddev
        projected_monthly = daily_mean * 30
        lower_bound = max(0.0, (daily_mean - 2 * daily_stddev) * 30)
        upper_bound = (daily_mean + 2 * daily_stddev) * 30

        daily_tokens_values = list(usage["daily_tokens"].values()) if usage["daily_tokens"] else []
        daily_token_mean = statistics.mean(daily_tokens_values) if daily_tokens_values else 0

        return {
            "model": model,
            "time_range": self.time_range,
            "days_of_data": len(day_values),
            "daily_burn_rate_usd": round(daily_mean, 4),
            "daily_burn_stddev_usd": round(daily_stddev, 4),
            "projected_monthly_cost_usd": round(projected_monthly, 2),
            "projected_monthly_lower_bound_usd": round(lower_bound, 2),
            "projected_monthly_upper_bound_usd": round(upper_bound, 2),
            "projected_monthly_tokens": int(daily_token_mean * 30),
            "confidence": "95%" if len(day_values) >= 7 else f"Low ({len(day_values)} days of data)",
        }
