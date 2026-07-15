"""Smart Alerting Manager for Agent Tracer Plus."""

import asyncio
import json
import logging
import urllib.error
import urllib.request
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class AlertCondition:
    def __init__(self, key: str, operator: str, value: Any):
        self.key = key
        self.operator = operator
        self.value = value

    def evaluate(self, trace_data: Dict[str, Any]) -> bool:
        actual = trace_data.get(self.key)
        if actual is None:
            return False

        if self.operator == ">":
            return actual > self.value
        elif self.operator == "<":
            return actual < self.value
        elif self.operator == "==":
            return actual == self.value
        elif self.operator == "!=":
            return actual != self.value
        return False

from agent_tracer_plus.alerts.channels import AlertChannel, SlackChannel, PagerDutyChannel, WebhookChannel

class AlertManager:
    """Evaluates traces against rules and dispatches alerts with debouncing."""

    def __init__(self, rules: List[Dict[str, Any]] = None):
        self.rules = rules or []
        # format: {"name": "High Cost", "condition": AlertCondition("total_cost", ">", 0.1), "destinations": [SlackDestination(...)], "cooldown_seconds": 300}
        self._last_alert_time: Dict[str, float] = {}

    async def process_trace(self, trace_data: Dict[str, Any]):
        now = time.time()
        for rule in self.rules:
            rule_name = rule.get("name", "Unnamed Rule")
            cooldown = rule.get("cooldown_seconds", 300) # Default 5 minutes
            
            # Check Debounce
            last_time = self._last_alert_time.get(rule_name, 0)
            if (now - last_time) < cooldown:
                continue # Skip alerting to prevent fatigue

            condition = rule.get("condition")
            if condition and condition.evaluate(trace_data):
                self._last_alert_time[rule_name] = now
                dests = rule.get("destinations", [])
                for dest in dests:
                    if hasattr(dest, 'send') and asyncio.iscoroutinefunction(dest.send):
                        asyncio.create_task(dest.send(
                            subject=f"Alert Triggered: {rule_name}",
                            message=f"Trace {trace_data.get('trace_id')} breached threshold {condition.key} {condition.operator} {condition.value}. Actual: {trace_data.get(condition.key)}",
                            trace_data=trace_data
                        ))
                    else:
                        logger.warning(f"Destination {dest} is missing an async send method")
