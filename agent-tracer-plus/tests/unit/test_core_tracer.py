"""Tests for AgentTracerPlus — initialization, storage parsing, sampling, PII masking."""

import pytest

from agent_tracer_plus.core.config import TracerConfig
from agent_tracer_plus.core.models import Span, SpanStatus, Trace, TraceStatus, TokenUsage, CostInfo
from agent_tracer_plus.core.tracer import AgentTracerPlus
from agent_tracer_plus.storage.memory import InMemoryBackend
from agent_tracer_plus.storage.sqlite import SQLiteBackend
from agent_tracer_plus.storage.ndjson import NDJSONBackend


class TestTracerInit:
    def test_default_creates_memory(self):
        tracer = AgentTracerPlus(TracerConfig(enabled=False))
        assert isinstance(tracer._storage, InMemoryBackend)

    def test_memory_uri(self):
        tracer = AgentTracerPlus(TracerConfig(storage="memory://", enabled=False))
        assert isinstance(tracer._storage, InMemoryBackend)

    def test_ndjson_uri(self, tmp_path):
        tracer = AgentTracerPlus(TracerConfig(storage=f"ndjson://{tmp_path}/traces", enabled=False))
        assert isinstance(getattr(tracer._storage, "_original", tracer._storage), NDJSONBackend)

    def test_sqlite_uri(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        tracer = AgentTracerPlus(TracerConfig(storage=f"sqlite://{db_path}", enabled=False))
        assert isinstance(getattr(tracer._storage, "_original", tracer._storage), SQLiteBackend)

    def test_composite_storage(self):
        tracer = AgentTracerPlus(TracerConfig(
            storage=["memory://", "memory://"],
            enabled=False,
        ))
        from agent_tracer_plus.storage.composite import CompositeBackend
        assert isinstance(getattr(tracer._storage, "_original", tracer._storage), CompositeBackend)

    def test_storage_instance_passthrough(self):
        backend = InMemoryBackend()
        tracer = AgentTracerPlus(TracerConfig(storage=backend, enabled=False))
        assert tracer._storage is backend

    def test_kwargs_init(self):
        tracer = AgentTracerPlus(service_name="test-svc", enabled=False, storage="memory://")
        assert tracer.config.service_name == "test-svc"
        assert isinstance(tracer._storage, InMemoryBackend)


class TestTracerSampling:
    def test_sampler_drops_at_zero(self):
        tracer = AgentTracerPlus(TracerConfig(
            sampling_rate=0.0,
            storage="memory://",
            enabled=True,
            auto_instrument=False,
        ))
        # Manually check if sampler drops
        trace = Trace(agent_name="test")
        trace.finish()
        assert tracer.sampler.should_sample(trace) is False

    def test_sampler_keeps_errors_at_zero(self):
        tracer = AgentTracerPlus(TracerConfig(
            sampling_rate=0.0,
            storage="memory://",
            enabled=True,
            auto_instrument=False,
        ))
        trace = Trace(agent_name="test", status=SpanStatus.ERROR)
        assert tracer.sampler.should_sample(trace) is True

    def test_sampler_keeps_all_at_one(self):
        tracer = AgentTracerPlus(TracerConfig(
            sampling_rate=1.0,
            storage="memory://",
            enabled=True,
            auto_instrument=False,
        ))
        trace = Trace(agent_name="test")
        assert tracer.sampler.should_sample(trace) is True


class TestTracerEnqueue:
    def test_enqueue_disabled(self):
        tracer = AgentTracerPlus(TracerConfig(
            storage="memory://",
            enabled=False,
            auto_instrument=False,
        ))
        trace = Trace(agent_name="test")
        trace.finish()
        tracer._enqueue_trace(trace)
        # Nothing should be queued when disabled
        assert tracer._batch_processor.pending_count == 0

    def test_enqueue_span_disabled(self):
        tracer = AgentTracerPlus(TracerConfig(
            storage="memory://",
            enabled=False,
            auto_instrument=False,
        ))
        span = Span(name="test")
        span.finish()
        tracer._enqueue_span(span)
        assert tracer._batch_processor.pending_count == 0


class TestTracerPIIMasking:
    def test_pii_masking_configured(self):
        tracer = AgentTracerPlus(TracerConfig(
            storage="memory://",
            pii_redaction=True,
            enabled=True,
            auto_instrument=False,
        ))
        assert tracer.pii_masker is not None

    def test_pii_masking_not_configured(self):
        tracer = AgentTracerPlus(TracerConfig(
            storage="memory://",
            pii_redaction=False,
            enabled=True,
            auto_instrument=False,
        ))
        assert tracer.pii_masker is None


class TestTracerBudget:
    def test_budget_configured(self):
        tracer = AgentTracerPlus(TracerConfig(
            storage="memory://",
            budget={"max_tokens_per_trace": 1000, "max_cost_per_trace": 1.0},
            enabled=True,
            auto_instrument=False,
        ))
        assert tracer.budget_enforcer is not None

    def test_budget_not_configured(self):
        tracer = AgentTracerPlus(TracerConfig(
            storage="memory://",
            enabled=True,
            auto_instrument=False,
        ))
        assert tracer.budget_enforcer is None


class TestTracerLifecycle:
    def test_start_sets_started(self):
        tracer = AgentTracerPlus(TracerConfig(
            storage="memory://",
            enabled=True,
            auto_instrument=False,
        ))
        tracer.start()
        assert tracer._started is True

    def test_double_start_is_noop(self):
        tracer = AgentTracerPlus(TracerConfig(
            storage="memory://",
            enabled=True,
            auto_instrument=False,
        ))
        tracer.start()
        tracer.start()  # Should not raise
        assert tracer._started is True

    @pytest.mark.asyncio
    async def test_shutdown(self):
        tracer = AgentTracerPlus(TracerConfig(
            storage="memory://",
            enabled=True,
            auto_instrument=False,
        ))
        tracer.start()
        await tracer.shutdown()
        assert tracer._started is False

    @pytest.mark.asyncio
    async def test_query_api(self):
        tracer = AgentTracerPlus(TracerConfig(
            storage="memory://",
            enabled=True,
            auto_instrument=False,
        ))
        results = await tracer.query()
        assert results == []

    @pytest.mark.asyncio
    async def test_get_trace_not_found(self):
        tracer = AgentTracerPlus(TracerConfig(
            storage="memory://",
            enabled=True,
            auto_instrument=False,
        ))
        result = await tracer.get_trace("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_spans_empty(self):
        tracer = AgentTracerPlus(TracerConfig(
            storage="memory://",
            enabled=True,
            auto_instrument=False,
        ))
        result = await tracer.get_spans("nonexistent")
        assert result == []

    @pytest.mark.asyncio
    async def test_storage_property(self):
        backend = InMemoryBackend()
        tracer = AgentTracerPlus(TracerConfig(
            storage=backend,
            enabled=True,
            auto_instrument=False,
        ))
        assert tracer.storage is backend
