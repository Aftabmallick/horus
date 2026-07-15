"""Token usage tracker for Agent Tracer Plus."""

import logging
from typing import Dict

from agent_tracer_plus.budget.enforcer import BudgetEnforcer

logger = logging.getLogger(__name__)


class UsageTracker:
    """Tracks token and cost usage across traces."""

    def __init__(self, enforcer: BudgetEnforcer | None = None):
        self.enforcer = enforcer
        # In a distributed system, this would be backed by Redis
        self._tenant_usage: Dict[str, Dict[str, float]] = {}
        self._agent_usage: Dict[str, Dict[str, float]] = {}

    def record_usage(self, trace_id: str,
                     tenant_id: str, agent_name: str,
                     tokens: int, cost: float) -> None:
        """Record usage and enforce budgets."""
        # Update tenant metrics
        if tenant_id:
            if tenant_id not in self._tenant_usage:
                self._tenant_usage[tenant_id] = {"tokens": 0, "cost": 0.0}
            self._tenant_usage[tenant_id]["tokens"] += tokens
            self._tenant_usage[tenant_id]["cost"] += cost

        # Update agent metrics
        if agent_name:
            if agent_name not in self._agent_usage:
                self._agent_usage[agent_name] = {"tokens": 0, "cost": 0.0}
            self._agent_usage[agent_name]["tokens"] += tokens
            self._agent_usage[agent_name]["cost"] += cost

        # Enforce budget if configured
        if self.enforcer:
            # We assume the enforcer maintains its own state or uses this one
            self.enforcer.check_budget(tokens, cost)

    def get_tenant_usage(self, tenant_id: str) -> Dict[str, float]:
        """Get current usage for a tenant."""
        return self._tenant_usage.get(tenant_id, {"tokens": 0, "cost": 0.0})

    def get_agent_usage(self, agent_name: str) -> Dict[str, float]:
        """Get current usage for an agent."""
        return self._agent_usage.get(agent_name, {"tokens": 0, "cost": 0.0})

    def reset(self) -> None:
        """Reset all usage metrics."""
        self._tenant_usage.clear()
        self._agent_usage.clear()
