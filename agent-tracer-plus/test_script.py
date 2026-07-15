from agent_tracer_plus.core.models import Span, Trace, SpanType
from agent_tracer_plus.intelligence.anomaly import AnomalyDetector

detector = AnomalyDetector()
current_trace = Trace(trace_id="current", agent_name="Agent")
current_spans = []
for i in range(3):
    span = Span(name="search_web", span_id=f"s_c{i}", span_type=SpanType.TOOL)
    span.input = '{"query": "weather"}'
    current_spans.append(span)

current_trace.spans = current_spans
anomalies = detector.detect_trace_anomalies(current_trace)
print(anomalies)
