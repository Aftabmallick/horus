"""OpenTelemetry (OTLP) storage backend."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.base import StorageBackend
from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("storage.otlp")


class OTLPBackend(StorageBackend):
    """Storage backend that forwards traces and spans to an OTLP endpoint (e.g., Datadog, Honeycomb, New Relic)."""

    def __init__(self, endpoint: str, service_name: str = "agent-tracer"):
        self.endpoint = endpoint
        self.service_name = service_name
        self._tracer_provider = None
        self._exporter = None
        self._span_processor = None
        self._tracer = None
        self._initialized = False

    async def _ensure_initialized(self):
        try:
            from opentelemetry import trace as otel_trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import SERVICE_NAME, Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
        except ImportError:
            raise ImportError("OpenTelemetry packages are required. Run `pip install agent-tracer-plus[otlp]`")

        if not self._initialized:
            resource = Resource(attributes={
                SERVICE_NAME: self.service_name
            })

            self._tracer_provider = TracerProvider(resource=resource)
            self._exporter = OTLPSpanExporter(endpoint=self.endpoint)
            self._span_processor = BatchSpanProcessor(self._exporter)
            self._tracer_provider.add_span_processor(self._span_processor)

            # Use our specific provider
            self._tracer = self._tracer_provider.get_tracer("agent_tracer_plus")
            self._initialized = True

    async def save_trace(self, trace: Trace) -> None:
        # In OTLP, traces are just collections of spans sharing a trace_id.
        # We don't need to explicitly "save" a trace object, but we could create a root span for it.
        # However, AgentTracerPlus already creates an AGENT root span for every trace.
        pass

    def _convert_timestamp(self, ts_str: Optional[str]) -> Optional[int]:
        if not ts_str:
            return None
        # OTel requires timestamps in nanoseconds since epoch
        dt = datetime.fromisoformat(ts_str)
        return int(dt.timestamp() * 1e9)

    async def save_span(self, span: Span) -> None:
        await self.save_spans_batch([span])

    async def save_spans_batch(self, spans: List[Span]) -> None:
        await self._ensure_initialized()
        from opentelemetry.sdk.trace import Span as OTelSpan
        from opentelemetry.trace import SpanContext, SpanKind, Status, StatusCode, TraceFlags

        for span in spans:
            # Reconstruct trace context
            trace_id_int = int(span.trace_id.replace("-", ""), 16) if "-" in span.trace_id else int(span.trace_id, 16)
            span_id_int = int(span.span_id.replace("-", ""), 16) if "-" in span.span_id else int(span.span_id, 16)

            # Map attributes
            attrs = dict(span.attributes)
            attrs["agent_tracer.span_type"] = span.span_type.value
            if span.input:
                attrs["agent_tracer.input"] = str(span.input)
            if span.output:
                attrs["agent_tracer.output"] = str(span.output)
            if span.token_usage:
                for k, v in span.token_usage.items():
                    attrs[f"llm.usage.{k}"] = v
            if span.cost_info:
                attrs["llm.cost"] = span.cost_info.get("total_cost", 0.0)

            context = SpanContext(
                trace_id=trace_id_int,
                span_id=span_id_int,
                is_remote=False,
                trace_flags=TraceFlags(0x01)
            )

            parent_context = None
            if span.parent_span_id:
                parent_span_id_int = int(span.parent_span_id.replace("-", ""), 16) if "-" in span.parent_span_id else int(span.parent_span_id, 16)
                parent_context = SpanContext(
                    trace_id=trace_id_int,
                    span_id=parent_span_id_int,
                    is_remote=False,
                    trace_flags=TraceFlags(0x01)
                )

            # Create the SDK Span directly since it's historical data
            start_time = self._convert_timestamp(span.started_at)
            end_time = self._convert_timestamp(span.ended_at)

            otel_span = OTelSpan(
                name=span.name,
                context=context,
                parent=parent_context,
                kind=SpanKind.INTERNAL,
                resource=self._tracer_provider.resource,
                start_time=start_time
            )

            otel_span.set_attributes(attrs)

            if span.status.value == "ERROR":
                otel_span.set_status(Status(StatusCode.ERROR, description=str(span.error)))
            elif span.status.value == "OK":
                otel_span.set_status(Status(StatusCode.OK))

            if end_time:
                otel_span.end(end_time=end_time)

            # Manually pass to processor
            self._span_processor.on_start(otel_span)
            if end_time:
                self._span_processor.on_end(otel_span)

    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        raise NotImplementedError("OTLP backend is write-only.")

    async def get_spans(self, trace_id: str) -> List[Span]:
        raise NotImplementedError("OTLP backend is write-only.")

    async def query_traces(self, filters: Dict[str, Any] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        raise NotImplementedError("OTLP backend is write-only.")

    async def delete_traces(self, before: datetime) -> int:
        raise NotImplementedError("Trace lifecycle is managed by the OTLP vendor.")

    async def flush(self) -> None:
        if self._span_processor:
            self._span_processor.force_flush()

    async def close(self) -> None:
        if self._span_processor:
            self._span_processor.shutdown()
        self._initialized = False

    async def health_check(self) -> bool:
        # In a real scenario, ping the OTLP endpoint
        return self._initialized
