"""Alerting rules engine."""

import logging
import time
from typing import Any, Callable, Dict, List

from agent_tracer_plus.alerts.channels import AlertChannel

logger = logging.getLogger(__name__)


class AlertRule:
    """A rule that triggers an alert based on trace statistics."""

    def __init__(
        self,
        condition: Callable[[Dict[str, Any]], bool],
        channels: List[AlertChannel],
        message_template: str,
        cooldown_seconds: int = 300,
    ):
        self.condition = condition
        self.channels = channels
        self.message_template = message_template
        self.cooldown_seconds = cooldown_seconds
        self.last_fired: float = 0.0

    def evaluate(self, stats: Dict[str, Any]) -> None:
        if self.condition(stats):
            current_time = time.time()
            if current_time - self.last_fired < self.cooldown_seconds:
                logger.debug("Alert condition met, but in cooldown period. Suppressing alert.")
                return

            self.last_fired = current_time
            message = self.message_template.format(**stats)

            for channel in self.channels:
                try:
                    channel.send("Agent Tracer Alert", message)
                except Exception as e:
                    logger.error(f"Failed to send alert via {channel.__class__.__name__}: {e}", exc_info=True)


class AlertEngine:
    """Evaluates rules against incoming trace data."""

    def __init__(self):
        self.rules: List[AlertRule] = []

    def add_rule(self, rule: AlertRule) -> None:
        self.rules.append(rule)

    def evaluate(self, stats: Dict[str, Any]) -> None:
        """Evaluate all rules against the provided stats (e.g. error_rate, latency)."""
        for rule in self.rules:
            rule.evaluate(stats)
