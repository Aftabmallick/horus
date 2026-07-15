import pytest

from agent_tracer_plus.core.models import Span, SpanType, Trace
from agent_tracer_plus.intelligence.replay import ReplayEngine
from agent_tracer_plus.storage.memory import InMemoryBackend


@pytest.mark.asyncio
async def test_replay_engine_matching():
    storage = InMemoryBackend()
    trace = Trace(trace_id="t1")
    
    # Create two mocked LLM spans
    s1 = Span(name="llm_1", trace_id="t1", span_type=SpanType.LLM, input={"prompt": "hello"}, output="world")
    s2 = Span(name="llm_2", trace_id="t1", span_type=SpanType.LLM, input={"prompt": "test"}, output="success")
    
    await storage.save_trace(trace)
    await storage.save_span(s1)
    await storage.save_span(s2)

    engine = ReplayEngine(trace_id="t1", storage=storage)
    await engine.load()

    assert len(engine._io_spans) == 2

    # Match exact first span
    should_mock, mock_out = engine.should_mock("LLM", "llm_1", {"prompt": "hello"})
    assert should_mock is True
    assert mock_out == "world"

    # Mismatch the second span (wrong input)
    should_mock, mock_out = engine.should_mock("LLM", "llm_2", {"prompt": "wrong"})
    assert should_mock is False
    assert engine.diverged is True

@pytest.mark.asyncio
async def test_replay_diverge_at():
    storage = InMemoryBackend()
    trace = Trace(trace_id="t1")
    
    s1 = Span(span_id="span1", name="llm_1", trace_id="t1", span_type=SpanType.LLM, input="1", output="A")
    s2 = Span(span_id="span2", name="llm_2", trace_id="t1", span_type=SpanType.LLM, input="2", output="B")
    
    await storage.save_trace(trace)
    await storage.save_span(s1)
    await storage.save_span(s2)

    # Tell it to diverge AT span1 (diverges immediately after span1 is processed)
    engine = ReplayEngine(trace_id="t1", storage=storage, diverge_span_id="span1")
    await engine.load()

    # The first call matches and returns output, but sets diverged=True
    should_mock, mock_out = engine.should_mock("LLM", "llm_1", "1")
    assert should_mock is True
    assert mock_out == "A"
    assert engine.diverged is True

    # The next call is rejected because we've diverged
    should_mock, mock_out = engine.should_mock("LLM", "llm_2", "2")
    assert should_mock is False

@pytest.mark.asyncio
async def test_tracer_check_replay():
    from agent_tracer_plus.core.tracer import AgentTracerPlus
    from agent_tracer_plus.core.config import TracerConfig

    storage = InMemoryBackend()
    trace = Trace(trace_id="t1")
    s1 = Span(span_id="s1", name="llm_1", trace_id="t1", span_type=SpanType.LLM, input="1", output="A")
    await storage.save_trace(trace)
    await storage.save_span(s1)

    config = TracerConfig(replay_trace_id="t1", storage=storage)
    tracer = AgentTracerPlus(config=config)
    await tracer.replay_engine.load()

    should_mock, out = tracer.check_replay("LLM", "llm_1", "1")
    assert should_mock is True
    assert out == "A"

    # Next one diverges since there are no more spans
    should_mock, out = tracer.check_replay("LLM", "llm_2", "2")
    assert should_mock is False
    assert tracer.replay_engine.diverged is True
