import pytest

from agent_tracer_plus.sustainability.carbon import CarbonTracker


@pytest.mark.asyncio
async def test_carbon_tracker():
    tracker = CarbonTracker(region="us-east-1")

    res = await tracker.calculate_footprint("gpt-4o", total_tokens=10000)
    assert res["co2_grams"] > 0
    assert res["energy_kwh"] == 10000 / 1000.0 * 0.005
    assert res["region"] == "us-east-1"

    res_mini = await tracker.calculate_footprint("gpt-4o-mini", total_tokens=10000)
    # gpt-4o-mini: 0.0015 kWh per 1k tokens (more efficient than standard, less than haiku)
    assert res_mini["energy_kwh"] == 10000 / 1000.0 * 0.0015
