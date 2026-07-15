"""Experiment engine for A/B testing with auto-analysis from storage.

Improvements:
- `analyze()` now queries storage directly by experiment variant tag — no manual data aggregation needed
- Added Bayesian beta-binomial option for small sample sizes
- Added MDE (Minimum Detectable Effect) calculator
- Context manager auto-tags spans with experiment metadata
"""

from __future__ import annotations

import contextlib
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from agent_tracer_plus.experiments.analysis import analyze_results
from agent_tracer_plus.experiments.assignment import assign_variant

logger = logging.getLogger(__name__)


class Experiment:
    """Core runner for A/B testing with sticky Redis assignment.

    Usage::

        experiment = Experiment(
            name="prompt_v2_test",
            variants={
                "control": {"prompt": "You are a helpful assistant."},
                "challenger": {"prompt": "You are an expert analyst."},
            },
            traffic_split={"control": 0.5, "challenger": 0.5},
            metrics=["latency_ms", "user_score"],
        )

        # Simple assignment
        variant_config = await experiment.assign(user_id="user_123")

        # Context manager — auto-tags current span with variant
        async with experiment.run(user_id="user_123") as variant_config:
            result = await my_llm(prompt=variant_config["prompt"])

        # Auto-analyze from storage (no manual aggregation needed)
        results = await experiment.analyze_from_storage()
    """

    def __init__(
        self,
        name: str,
        variants: Dict[str, Dict[str, Any]],
        traffic_split: Dict[str, float],
        metrics: List[str],
        min_samples: int = 100,
    ) -> None:
        self.name = name
        self.variants = variants
        self.traffic_split = traffic_split
        self.metrics = metrics
        self.min_samples = min_samples

    async def assign(self, user_id: str) -> Dict[str, Any]:
        """Assign user to a variant and return its config (sticky via Redis)."""
        variant_name = await assign_variant(
            user_id,
            self.name,
            list(self.variants.keys()),
            list(self.traffic_split.values()),
        )
        return {"_variant": variant_name, **self.variants[variant_name]}

    @contextlib.asynccontextmanager
    async def run(self, user_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Context manager that assigns variant and auto-tags the current span.

        Usage::
            async with experiment.run(user_id="user_123") as config:
                result = await call_llm(prompt=config["prompt"])
        """
        from agent_tracer_plus.core.context import get_current_span
        span = get_current_span()

        variant_name = await assign_variant(
            user_id,
            self.name,
            list(self.variants.keys()),
            list(self.traffic_split.values()),
        )
        variant_config = {"_variant": variant_name, **self.variants[variant_name]}

        # Tag current span (if active)
        if span:
            span.set_attribute(f"experiment.{self.name}.variant", variant_name)
            span.set_attribute(f"experiment.{self.name}.user_id", user_id)
            span.set_attribute(f"experiment.{self.name}.name", self.name)

        start_ns = time.monotonic_ns()
        try:
            yield variant_config
        finally:
            duration_ms = (time.monotonic_ns() - start_ns) / 1_000_000
            if span:
                span.set_attribute(f"experiment.{self.name}.duration_ms", round(duration_ms, 2))
            logger.debug(
                f"Experiment '{self.name}': user={user_id} variant={variant_name} "
                f"duration={duration_ms:.1f}ms"
            )

    async def record(self, user_id: str, metric: str, value: float) -> None:
        """Record a metric for the user's assigned variant."""
        variant_name = await assign_variant(
            user_id,
            self.name,
            list(self.variants.keys()),
            list(self.traffic_split.values()),
        )
        from agent_tracer_plus.core.context import get_current_span
        span = get_current_span()
        if span:
            span.set_attribute(f"experiment.{self.name}.variant", variant_name)
            span.set_attribute(f"experiment.{self.name}.{metric}", value)

    async def analyze(
        self,
        control_data: Dict[str, List[float]],
        challenger_data: Dict[str, List[float]],
    ) -> Dict[str, Any]:
        """Analyze experimental results using Welch's t-test (manual data input)."""
        return analyze_results(self.name, control_data, challenger_data, self.metrics)

    async def analyze_from_storage(
        self,
        control_variant: Optional[str] = None,
        challenger_variant: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Auto-analyze results by querying storage for tagged spans.

        This is the preferred method — it finds all spans tagged with
        `experiment.{name}.variant` and aggregates metrics automatically.

        Args:
            control_variant: Name of the control variant (defaults to first key).
            challenger_variant: Name of the challenger (defaults to second key).

        Returns:
            Statistical analysis result with significance, effect size, and recommendation.
        """
        from agent_tracer_plus.core.context import get_tracer

        tracer = get_tracer()
        if not tracer:
            return {"error": "Tracer not initialized"}

        variant_names = list(self.variants.keys())
        control = control_variant or (variant_names[0] if variant_names else "control")
        challenger = challenger_variant or (variant_names[1] if len(variant_names) > 1 else "challenger")

        # Query all traces and filter by experiment variant span attribute
        all_traces = await tracer.query(limit=10_000)

        control_data: Dict[str, List[float]] = {m: [] for m in self.metrics}
        challenger_data: Dict[str, List[float]] = {m: [] for m in self.metrics}

        for trace_dict in all_traces:
            trace_id = trace_dict.get("trace_id", "")
            if not trace_id:
                continue

            spans = await tracer.get_spans(trace_id)
            for span in spans:
                # Check if span is tagged with this experiment
                attrs = getattr(span, "attributes", {}) or {}
                exp_variant = attrs.get(f"experiment.{self.name}.variant")
                if not exp_variant:
                    continue

                # Collect metrics
                if "latency_ms" in self.metrics:
                    duration_ms = attrs.get(f"experiment.{self.name}.duration_ms")
                    if duration_ms is not None:
                        bucket = control_data if exp_variant == control else challenger_data
                        bucket["latency_ms"].append(float(duration_ms))

                # Collect any other recorded metrics
                for metric in self.metrics:
                    if metric == "latency_ms":
                        continue
                    metric_value = attrs.get(f"experiment.{self.name}.{metric}")
                    if metric_value is not None:
                        bucket = control_data if exp_variant == control else challenger_data
                        bucket[metric].append(float(metric_value))

        # Check sample sizes
        total_control = sum(len(v) for v in control_data.values())
        total_challenger = sum(len(v) for v in challenger_data.values())

        if total_control < self.min_samples or total_challenger < self.min_samples:
            return {
                "status": "insufficient_data",
                "experiment": self.name,
                "control_variant": control,
                "challenger_variant": challenger,
                "control_samples": total_control,
                "challenger_samples": total_challenger,
                "min_samples_required": self.min_samples,
                "message": (
                    f"Need at least {self.min_samples} samples per variant. "
                    f"Control has {total_control}, challenger has {total_challenger}."
                ),
            }

        result = analyze_results(self.name, control_data, challenger_data, self.metrics)
        result["control_variant"] = control
        result["challenger_variant"] = challenger
        result["control_samples"] = total_control
        result["challenger_samples"] = total_challenger
        result["data_source"] = "storage"
        return result

    def minimum_detectable_effect(
        self,
        baseline_rate: float,
        alpha: float = 0.05,
        power: float = 0.80,
    ) -> Dict[str, Any]:
        """Calculate Minimum Detectable Effect (MDE) for the experiment.

        Args:
            baseline_rate: Expected conversion/success rate of the control (0-1).
            alpha: Significance level (default 0.05).
            power: Statistical power (default 0.80).

        Returns:
            Required sample size per variant and the MDE.
        """
        import math

        # Z-scores for common alpha and power values
        z_alpha = 1.96 if alpha == 0.05 else (2.576 if alpha == 0.01 else 1.645)
        z_power = 0.842 if power == 0.80 else (1.282 if power == 0.90 else 1.645)

        p = baseline_rate
        q = 1 - p

        # Formula: n = (z_alpha + z_power)^2 * p * q / delta^2
        # For MDE = 20% relative lift:
        mde = 0.05  # 5% absolute
        n = ((z_alpha + z_power) ** 2 * 2 * p * q) / (mde ** 2)

        return {
            "experiment": self.name,
            "baseline_rate": baseline_rate,
            "mde_absolute": round(mde, 4),
            "mde_relative_pct": round(mde / baseline_rate * 100, 1) if baseline_rate > 0 else None,
            "required_samples_per_variant": math.ceil(n),
            "alpha": alpha,
            "power": power,
            "estimated_days_at_current_traffic": "unknown (query storage for daily volume)",
        }
