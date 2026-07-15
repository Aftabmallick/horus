"""Sustainability reporting."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from agent_tracer_plus.core.tracer import AgentTracerPlus

logger = logging.getLogger(__name__)


async def generate_sustainability_report(storage_uri: str, time_range: str = "last_30d") -> Dict[str, Any]:
    """Generate a high-level sustainability report from actual trace data."""
    logger.info(f"Generating sustainability report for {time_range}")

    # Parse time_range (simple implementation)
    days = 30
    if time_range.startswith("last_") and time_range.endswith("d"):
        try:
            days = int(time_range[5:-1])
        except ValueError:
            pass

    cutoff = datetime.utcnow() - timedelta(days=days)

    storage = AgentTracerPlus._storage_from_uri(storage_uri)

    traces = await storage.query_traces(limit=10000)

    total_co2_grams = 0.0
    total_energy_kwh = 0.0

    for trace in traces:
        metadata = trace.get("metadata", {})
        carbon_info = metadata.get("carbon", {})
        if carbon_info:
            total_co2_grams += carbon_info.get("co2_grams", 0.0)
            total_energy_kwh += carbon_info.get("energy_kwh", 0.0)

    total_co2_kg = total_co2_grams / 1000.0

    # Contextual equivalencies
    # 1 mile in a gas car = ~404 grams CO2
    miles_driven = total_co2_grams / 404.0

    return {
        "total_co2_kg": round(total_co2_kg, 4),
        "total_energy_kwh": round(total_energy_kwh, 4),
        "equivalent": f"Driving {round(miles_driven, 2)} miles in a gas car"
    }
