from agent_tracer_plus.core.models import SpanStatus, Trace
from agent_tracer_plus.processing.sampling import Sampler


def test_sampler_rate():
    sampler_all = Sampler(rate=1.0)
    assert sampler_all.should_sample(Trace(trace_id="1")) is True

    sampler_none = Sampler(rate=0.0)
    assert sampler_none.should_sample(Trace(trace_id="2")) is False

def test_sampler_conditional():
    # Base rate is 0%, but we always sample ERROR traces
    sampler = Sampler(
        rate=0.0,
        conditional=lambda t: t.status == SpanStatus.ERROR
    )

    trace_ok = Trace(trace_id="3", status=SpanStatus.OK)
    assert sampler.should_sample(trace_ok) is False

    trace_err = Trace(trace_id="4", status=SpanStatus.ERROR)
    assert sampler.should_sample(trace_err) is True
