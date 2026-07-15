"""Unit tests for the Anomaly Detection engine."""

from agent_tracer_plus.core.models import Span, Trace, SpanType
from agent_tracer_plus.intelligence.anomaly import AnomalyDetector


def test_anomaly_detector_loop_detection():
    detector = AnomalyDetector()
    
    # Current trace where `search_web` is called 3 times (a loop)
    current_trace = Trace(trace_id="current", agent_name="Agent")
    current_spans = []
    for i in range(3):
        span = Span(name="search_web", span_id=f"s_c{i}", span_type=SpanType.TOOL)
        span.input = '{"query": "weather"}'
        current_spans.append(span)
    
    current_trace.spans = current_spans
    
    anomalies = detector.detect_trace_anomalies(current_trace)
    
    # Expect 1 anomaly for loop detection
    loop_anomalies = [a for a in anomalies if a.anomaly_type == "infinite_loop"]
    assert len(loop_anomalies) == 1
    assert loop_anomalies[0].details["tool_name"] == "search_web"


def test_anomaly_detector_latency_spike():
    detector = AnomalyDetector(ewma_alpha=0.5, latency_threshold_stddev=2.0)
    
    # Send a few normal traces to build EWMA with some variance (stddev > 10ms)
    durations = [100.0, 130.0, 70.0, 140.0, 60.0]  # ms
    for i, dur in enumerate(durations):
        t = Trace(trace_id=f"t{i}", agent_name="Agent", started_at=100.0, ended_at=100.0 + (dur / 1000.0))
        detector.detect_trace_anomalies(t)
    
    # Send an outlier
    t_outlier = Trace(trace_id="outlier", agent_name="Agent", started_at=100.0, ended_at=102.0) # 2000ms
    anomalies = detector.detect_trace_anomalies(t_outlier)
    
    spike_anomalies = [a for a in anomalies if a.anomaly_type == "latency_spike"]
    assert len(spike_anomalies) == 1


def test_anomaly_detector_excessive_tools():
    detector = AnomalyDetector()
    
    current_trace = Trace(trace_id="current", agent_name="Agent")
    current_spans = []
    for i in range(16):
        span = Span(name=f"tool_{i}", span_id=f"s_c{i}", span_type=SpanType.TOOL)
        current_spans.append(span)
    
    current_trace.spans = current_spans
    
    anomalies = detector.detect_trace_anomalies(current_trace)
    
    excessive = [a for a in anomalies if a.anomaly_type == "excessive_tool_usage"]
    assert len(excessive) == 1
