import pytest

from agent_tracer_plus.sla.monitor import SLAMonitor


@pytest.mark.asyncio
async def test_sla_monitor_compliance():
    monitor = SLAMonitor()
    monitor.add_sla("agent1", "p99_latency", 2.0)
    monitor.add_sla("agent1", "success_rate", 0.95)

    # Test pass
    stats_pass = {"agent1": {"p99_latency": 1.5, "success_rate": 0.99}}
    assert await monitor.check_compliance(stats_pass) is True

    # Test breach latency
    stats_breach_lat = {"agent1": {"p99_latency": 2.5, "success_rate": 0.99}}
    assert await monitor.check_compliance(stats_breach_lat) is False

    # Test breach success
    stats_breach_succ = {"agent1": {"p99_latency": 1.5, "success_rate": 0.90}}
    assert await monitor.check_compliance(stats_breach_succ) is False

    # Test missing metric with a fresh monitor to avoid sliding window pollution
    monitor_fresh = SLAMonitor()
    monitor_fresh.add_sla("agent1", "p99_latency", 2.0)
    monitor_fresh.add_sla("agent1", "success_rate", 0.95)
    stats_missing = {"agent1": {"p99_latency": 1.5}}
    assert await monitor_fresh.check_compliance(stats_missing) is True
