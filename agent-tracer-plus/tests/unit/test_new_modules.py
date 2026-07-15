"""Tests for all newly completed modules."""

import asyncio

import pytest

# ── Propagation Tests ──


class TestB3Propagation:
    def test_inject_multi_header(self):
        from agent_tracer_plus.propagation.b3 import B3Propagator

        propagator = B3Propagator()
        # Without active trace, injection should be a no-op
        headers = propagator.inject({})
        assert "X-B3-TraceId" not in headers

    def test_extract_multi_header(self):
        from agent_tracer_plus.propagation.b3 import B3Propagator

        propagator = B3Propagator()
        headers = {
            "X-B3-TraceId": "abcdef1234567890abcdef1234567890",
            "X-B3-SpanId": "1234567890abcdef",
            "X-B3-Sampled": "1",
        }
        ctx = propagator.extract(headers)
        assert ctx is not None
        assert ctx.trace_id == "abcdef1234567890abcdef1234567890"
        assert ctx.span_id == "1234567890abcdef"
        assert ctx.sampled is True

    def test_extract_single_header(self):
        from agent_tracer_plus.propagation.b3 import B3Propagator

        propagator = B3Propagator()
        headers = {"b3": "abcdef1234567890abcdef1234567890-1234567890abcdef-1"}
        ctx = propagator.extract(headers)
        assert ctx is not None
        assert ctx.trace_id == "abcdef1234567890abcdef1234567890"
        assert ctx.sampled is True

    def test_extract_deny(self):
        from agent_tracer_plus.propagation.b3 import B3Propagator

        propagator = B3Propagator()
        ctx = propagator.extract({"b3": "0"})
        assert ctx is not None
        assert ctx.sampled is False


class TestBaggagePropagation:
    def test_inject_and_extract(self):
        from agent_tracer_plus.propagation.baggage import Baggage, BaggagePropagator

        propagator = BaggagePropagator()
        baggage = Baggage({"user_id": "u_123", "tenant": "acme"})

        headers = propagator.inject(baggage, {})
        assert "baggage" in headers
        assert "user_id" in headers["baggage"]
        assert "tenant" in headers["baggage"]

        extracted = propagator.extract(headers)
        assert extracted.get("user_id") == "u_123"
        assert extracted.get("tenant") == "acme"

    def test_empty_baggage(self):
        from agent_tracer_plus.propagation.baggage import Baggage, BaggagePropagator

        propagator = BaggagePropagator()
        baggage = Baggage()
        headers = propagator.inject(baggage, {})
        assert "baggage" not in headers

    def test_max_entries(self):
        from agent_tracer_plus.propagation.baggage import Baggage

        baggage = Baggage()
        for i in range(200):
            baggage.set(f"key_{i}", f"val_{i}")
        assert len(baggage) == 180  # Capped at max


# ── Query Module Tests ──


class TestTraceFilter:
    def test_build_filter(self):
        from agent_tracer_plus.query.filters import build_filter

        f = build_filter(service_name="my-app", status="ERROR", has_errors=True)
        assert f.service_name == "my-app"
        assert f.status == "ERROR"
        assert f.has_errors is True

    def test_filter_matches(self):
        from agent_tracer_plus.query.filters import TraceFilter

        f = TraceFilter(service_name="my-app", status="COMPLETED")
        assert f.matches({"service_name": "my-app", "status": "COMPLETED"})
        assert not f.matches({"service_name": "other-app", "status": "COMPLETED"})
        assert not f.matches({"service_name": "my-app", "status": "ERROR"})

    def test_filter_with_tags(self):
        from agent_tracer_plus.query.filters import TraceFilter

        f = TraceFilter(tags=["high-priority", "production"])
        assert f.matches({"tags": ["high-priority", "production", "v2"]})
        assert not f.matches({"tags": ["low-priority"]})

    def test_filter_time_range(self):
        from agent_tracer_plus.query.filters import TraceFilter

        f = TraceFilter(time_range="last_7d")
        f.apply_time_range()
        assert f.since is not None


# ── Carbon Data Tests ──


class TestCarbonData:
    def test_get_carbon_intensity(self):
        from agent_tracer_plus.utils.carbon_data import get_carbon_intensity

        assert get_carbon_intensity("us-east-1") == 384.0
        assert get_carbon_intensity("eu-north-1") == 8.0
        assert get_carbon_intensity("unknown-region") == 400.0  # Default

    def test_get_model_energy(self):
        from agent_tracer_plus.utils.carbon_data import get_model_energy

        assert get_model_energy("gpt-4o") == 0.005
        assert get_model_energy("gpt-4o-mini") == 0.0015
        assert get_model_energy("some-mini-model") == 0.001  # Heuristic match


# ── Registry Tests ──


class TestInstrumentorRegistry:
    def test_register_and_list(self):
        from agent_tracer_plus.auto.registry import InstrumentorRegistry

        registry = InstrumentorRegistry()
        registry.register("test", "os", lambda: None, priority=10)
        assert len(registry.entries) == 1
        assert registry.entries[0].name == "test"

    def test_is_installed(self):
        from agent_tracer_plus.auto.registry import InstrumentorRegistry

        registry = InstrumentorRegistry()
        assert registry.is_installed("os") is True
        assert registry.is_installed("nonexistent_fake_module") is False

    def test_apply_all_with_config_flag(self):
        from agent_tracer_plus.auto.registry import InstrumentorRegistry
        from agent_tracer_plus.core.config import TracerConfig

        registry = InstrumentorRegistry()
        called = []
        registry.register("os_test", "os", lambda: called.append("os"), config_flag="instrument_openai", priority=10)

        # Config with instrument_openai=False → should skip
        config = TracerConfig(instrument_openai=False)
        result = registry.apply_all(config)
        assert result == []
        assert called == []

        # Config with instrument_openai=True → should apply
        config2 = TracerConfig(instrument_openai=True)
        result2 = registry.apply_all(config2)
        assert result2 == ["os_test"]
        assert called == ["os"]


# ── Annotations Tests ──


class TestAnnotations:
    @pytest.mark.asyncio
    async def test_annotate_and_query(self):
        from agent_tracer_plus.feedback.annotations import AnnotationStore

        store = AnnotationStore()
        ann = store.add("trace-1", "aftab@test.com", "Found a bug", tags=["bug"], status="investigating")
        assert ann.trace_id == "trace-1"
        assert ann.author == "aftab@test.com"
        assert ann.status == "investigating"

        results = store.get_for_trace("trace-1")
        assert len(results) == 1

        queried = store.query(tags=["bug"])
        assert len(queried) == 1

        queried_empty = store.query(tags=["nonexistent"])
        assert len(queried_empty) == 0

    @pytest.mark.asyncio
    async def test_update_and_delete(self):
        from agent_tracer_plus.feedback.annotations import AnnotationStore

        store = AnnotationStore()
        ann = store.add("trace-2", "dev@test.com", "Investigating", status="open")

        assert store.update_status(ann.annotation_id, "resolved")
        assert store.get_for_trace("trace-2")[0].status == "resolved"

        assert store.delete(ann.annotation_id)
        assert len(store.get_for_trace("trace-2")) == 0


# ── Memory Tracer Tests ──


class TestAgentMemoryTracer:
    def test_write_read_delete(self):
        from agent_tracer_plus.sessions.memory import AgentMemoryTracer

        tracer = AgentMemoryTracer()
        tracer.trace_write("user_pref", "dark mode", memory_type="long_term")
        tracer.trace_write("last_query", "hello world", memory_type="short_term")

        read_op = tracer.trace_read("user_pref", memory_type="long_term")
        assert read_op.hit is True
        assert read_op.staleness_seconds is not None

        miss_op = tracer.trace_read("nonexistent")
        assert miss_op.hit is False

        tracer.trace_delete("user_pref")
        read_after_delete = tracer.trace_read("user_pref")
        assert read_after_delete.hit is False

    def test_stats(self):
        from agent_tracer_plus.sessions.memory import AgentMemoryTracer

        tracer = AgentMemoryTracer()
        tracer.trace_write("k1", "v1")
        tracer.trace_write("k2", "v2")
        tracer.trace_read("k1")
        tracer.trace_read("k3")  # miss

        stats = tracer.get_stats()
        assert stats["writes"] == 2
        assert stats["reads"] == 2
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1
        assert stats["hit_rate_pct"] == 50.0
        assert stats["active_memories"] == 2


# ── Shadow Deploy Tests ──


class TestShadowDeploy:
    @pytest.mark.asyncio
    async def test_shadow_returns_primary(self):
        from agent_tracer_plus.experiments.shadow import ShadowDeploy

        async def primary(x):
            return x * 2

        async def shadow(x):
            return x * 3

        deploy = ShadowDeploy(primary, shadow)
        result = await deploy(5)
        assert result == 10  # Always returns primary

        # Give shadow time to complete
        await asyncio.sleep(0.1)
        stats = deploy.get_comparison_stats()
        assert stats["total_comparisons"] == 1
        assert stats["mismatch_count"] == 1


# ── What-If Engine Tests ──


class TestWhatIfEngine:
    def test_init(self):
        from agent_tracer_plus.simulator.what_if import WhatIfEngine
        engine = WhatIfEngine()
        assert engine is not None


# ── Cost Simulator Tests ──


class TestCostSimulator:
    def test_init(self):
        from agent_tracer_plus.simulator.cost_sim import CostSimulator
        sim = CostSimulator(time_range="last_30d")
        assert sim.time_range == "last_30d"


# ── Docs Generator Tests ──


class TestDocsGenerator:
    @pytest.mark.asyncio
    async def test_no_tracer(self):
        import agent_tracer_plus
        old_tracer = agent_tracer_plus._tracer
        agent_tracer_plus._tracer = None
        try:
            from agent_tracer_plus.docs_gen.generator import generate_docs
            result = await generate_docs("TestAgent")
            assert "TestAgent" in result
            assert "No tracer initialized" in result
        finally:
            agent_tracer_plus._tracer = old_tracer


# ── SLA Reporter Tests ──


class TestSLAReporter:
    def test_metric_calculation(self):
        from agent_tracer_plus.sla.reporter import SLAReporter

        reporter = SLAReporter()
        stats = {"total": 100, "errors": 5, "durations": list(range(100)), "costs": [0.01] * 100}

        success_rate = reporter._calculate_metric("success_rate", stats)
        assert success_rate == 95.0

        error_rate = reporter._calculate_metric("error_rate", stats)
        assert error_rate == 5.0

    def test_compliance_check(self):
        from agent_tracer_plus.sla.reporter import SLAReporter

        reporter = SLAReporter()
        assert reporter._check_compliance("success_rate", 99.5, 99.0) is True
        assert reporter._check_compliance("success_rate", 98.0, 99.0) is False
        assert reporter._check_compliance("error_rate", 0.5, 1.0) is True
        assert reporter._check_compliance("error_rate", 2.0, 1.0) is False
