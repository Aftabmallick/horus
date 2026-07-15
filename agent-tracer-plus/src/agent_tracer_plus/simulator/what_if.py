"""What-if scenario engine for traces."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from agent_tracer_plus.core.context import get_tracer
from agent_tracer_plus.utils.pricing import get_model_pricing

logger = logging.getLogger(__name__)


class WhatIfEngine:
    """Engine for what-if scenarios (latency, cost, throughput).

    Allows hypothetical analysis like:
      - "What if latency was 2x slower?"
      - "What if we added caching and reduced token usage by 40%?"
      - "What if error rate doubles?"
    """

    def __init__(self) -> None:
        pass

    async def run_scenario(self, scenario_config: Dict[str, Any]) -> Dict[str, Any]:
        """Run a what-if scenario against historical trace data.

        Args:
            scenario_config: Dict with keys like:
                - latency_multiplier: float (e.g. 2.0 = double latency)
                - token_reduction_pct: float (e.g. 40.0 = 40% fewer tokens)
                - error_rate_multiplier: float (e.g. 2.0 = double errors)
                - model_swap: str (e.g. "gpt-4o-mini" = swap to this model)
                - budget_cap_usd: float (e.g. 100.0 = $100 budget)
        """
        tracer = get_tracer()
        if not tracer:
            return {"error": "Tracer not initialized"}

        traces = await tracer.query(limit=5000)
        if not traces:
            return {"status": "no_data", "message": "No traces to analyze"}

        # Current state
        total_traces = len(traces)
        total_cost = sum(t.get("total_cost", 0) for t in traces)
        total_tokens = sum(t.get("total_tokens", 0) for t in traces)
        total_errors = sum(t.get("error_count", 0) for t in traces)
        avg_duration = sum(t.get("duration_ms", 0) for t in traces) / total_traces
        error_rate = total_errors / total_traces * 100 if total_traces else 0

        result: Dict[str, Any] = {
            "scenario": scenario_config,
            "baseline": {
                "total_traces": total_traces,
                "total_cost_usd": round(total_cost, 4),
                "total_tokens": total_tokens,
                "avg_duration_ms": round(avg_duration, 2),
                "error_rate_pct": round(error_rate, 2),
            },
            "projected": {},
        }

        # Apply scenario modifiers
        proj_cost = total_cost
        proj_tokens = total_tokens
        proj_duration = avg_duration
        proj_error_rate = error_rate
        impacts: List[str] = []

        # Latency multiplier
        if "latency_multiplier" in scenario_config:
            mult = scenario_config["latency_multiplier"]
            proj_duration *= mult
            impacts.append(f"Latency {'increased' if mult > 1 else 'decreased'} to {round(proj_duration, 2)}ms ({mult}x)")

        # Token reduction
        if "token_reduction_pct" in scenario_config:
            pct = scenario_config["token_reduction_pct"]
            factor = 1 - (pct / 100.0)
            proj_tokens = int(proj_tokens * factor)
            proj_cost *= factor
            impacts.append(f"Tokens reduced by {pct}% → {proj_tokens} tokens, cost → ${round(proj_cost, 4)}")

        # Error rate multiplier
        if "error_rate_multiplier" in scenario_config:
            mult = scenario_config["error_rate_multiplier"]
            proj_error_rate *= mult
            impacts.append(f"Error rate {'increased' if mult > 1 else 'decreased'} to {round(proj_error_rate, 2)}%")

        # Model swap
        if "model_swap" in scenario_config:
            new_model = scenario_config["model_swap"]
            pricing = get_model_pricing(new_model)
            if pricing:
                # Rough: assume 60/40 input/output split
                inp_tokens = int(proj_tokens * 0.6)
                out_tokens = int(proj_tokens * 0.4)
                proj_cost = pricing.calculate_cost(inp_tokens, out_tokens)
                impacts.append(f"Model swapped to {new_model} → cost ${round(proj_cost, 4)}")

        # Budget cap
        budget_exceeded = False
        if "budget_cap_usd" in scenario_config:
            cap = scenario_config["budget_cap_usd"]
            if proj_cost > cap:
                budget_exceeded = True
                impacts.append(f"⚠️  Projected cost ${round(proj_cost, 4)} EXCEEDS budget cap ${cap}")
            else:
                impacts.append(f"✅ Projected cost ${round(proj_cost, 4)} within budget cap ${cap}")

        result["projected"] = {
            "total_cost_usd": round(proj_cost, 4),
            "total_tokens": proj_tokens,
            "avg_duration_ms": round(proj_duration, 2),
            "error_rate_pct": round(proj_error_rate, 2),
            "budget_exceeded": budget_exceeded,
        }
        result["impacts"] = impacts
        result["cost_delta_usd"] = round(proj_cost - total_cost, 4)
        result["cost_delta_pct"] = round((proj_cost - total_cost) / total_cost * 100, 2) if total_cost > 0 else 0

        logger.info(f"What-if scenario completed: {len(impacts)} impacts calculated")
        return result
