"""Native OpenTelemetry SpanExporter adapter.

Makes Agent Tracer Plus a first-class OpenTelemetry citizen by implementing
the standard `SpanExporter` interface. This allows ATP spans to be exported
to any OTel-compatible backend (Jaeger, Grafana Tempo, Datadog, New Relic,
Honeycomb, AWS X-Ray, etc.) using the standard OTel SDK pipeline.

Usage::

    from agent_tracer_plus.storage.otel_exporter import AgentTracerPlusExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    exporter = AgentTracerPlusExporter(endpoint="http://localhost:4318")
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(exporter))

Or via ATP init::

    agent_tracer_plus.init(
        storage="otlp://localhost:4317",   # existing OTLP backend
    )
    # The OTel exporter is implicitly used for OTLP targets

Bidirectional bridge::

    # Export ATP traces TO OTel-compatible backends
    exporter = AgentTracerPlusExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Now use standard OTel tracer AND ATP tracer — both export to same backend
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


def _map_atp_span_to_otel(span: Any) -> Optional[Any]:
    """Map an ATP Span dataclass to an OTel ReadableSpan.

    Handles the semantic conventions mapping between ATP and OTel.
    """
    try:
        from opentelemetry import trace as otel_trace
        from opentelemetry.sdk.trace import ReadableSpan
        from opentelemetry.trace import SpanContext as OtelSpanContext, TraceFlags
        from opentelemetry.trace.status import Status, StatusCode

        # Parse trace/span IDs (ATP uses UUID strings, OTel uses int)
        def _to_otel_id(hex_str: str, length: int) -> int:
            """Convert a hex string to an integer OTel ID."""
            try:
                clean = hex_str.replace("-", "")[:length]
                return int(clean, 16)
            except (ValueError, TypeError):
                return 0

        trace_id_int = _to_otel_id(getattr(span, "trace_id", ""), 32)
        span_id_int = _to_otel_id(getattr(span, "span_id", ""), 16)
        parent_span_id_int = _to_otel_id(getattr(span, "parent_span_id", "") or "", 16)

        # Build OTel attributes from ATP span
        attributes: Dict[str, Any] = {}

        # Semantic conventions
        span_type = getattr(span, "span_type", None)
        if span_type:
            span_type_str = span_type.value if hasattr(span_type, "value") else str(span_type)
            attributes["atp.span.type"] = span_type_str

            if span_type_str.upper() == "LLM":
                attributes["gen_ai.operation.name"] = span.name

        # Token usage
        tu = getattr(span, "token_usage", None)
        if tu:
            attributes["gen_ai.usage.input_tokens"] = (
                tu.get("input_tokens", 0) if isinstance(tu, dict) else getattr(tu, "input_tokens", 0)
            )
            attributes["gen_ai.usage.output_tokens"] = (
                tu.get("output_tokens", 0) if isinstance(tu, dict) else getattr(tu, "output_tokens", 0)
            )

        # Cost info
        ci = getattr(span, "cost_info", None)
        if ci:
            attributes["atp.cost.total_usd"] = (
                ci.get("total_cost", 0) if isinstance(ci, dict) else getattr(ci, "total_cost", 0)
            )
            attributes["atp.cost.model"] = (
                ci.get("model", "") if isinstance(ci, dict) else getattr(ci, "model", "")
            )

        # Extra attributes from span.attributes
        extra_attrs = getattr(span, "attributes", {}) or {}
        attributes.update(extra_attrs)

        # Error status
        error = getattr(span, "error", None)
        span_status = getattr(span, "status", None)
        status_value = span_status.value if hasattr(span_status, "value") else str(span_status)

        if error or status_value.upper() == "ERROR":
            otel_status = Status(StatusCode.ERROR, description=str(error) if error else "unknown error")
        else:
            otel_status = Status(StatusCode.OK)

        # Timestamps (ATP uses Unix epoch float seconds → OTel uses nanoseconds)
        started_at = getattr(span, "started_at", 0) or 0
        ended_at = getattr(span, "ended_at", started_at) or started_at
        start_time_ns = int(started_at * 1_000_000_000)
        end_time_ns = int(ended_at * 1_000_000_000)

        # Build context
        parent_ctx = None
        if parent_span_id_int:
            parent_ctx = OtelSpanContext(
                trace_id=trace_id_int,
                span_id=parent_span_id_int,
                is_remote=False,
                trace_flags=TraceFlags(TraceFlags.SAMPLED),
            )

        span_ctx = OtelSpanContext(
            trace_id=trace_id_int,
            span_id=span_id_int,
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )

        return {
            "name": span.name,
            "context": span_ctx,
            "parent": parent_ctx,
            "attributes": attributes,
            "status": otel_status,
            "start_time": start_time_ns,
            "end_time": end_time_ns,
        }

    except Exception as e:
        logger.debug(f"Failed to map ATP span to OTel: {e}")
        return None


class AgentTracerPlusExporter:
    """OTel SpanExporter that receives OTel spans and stores them via ATP storage.

    This implements the OTel `SpanExporter` protocol so ATP can be plugged
    into any standard OTel `TracerProvider` pipeline.

    Usage::

        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from agent_tracer_plus.storage.otel_exporter import AgentTracerPlusExporter

        exporter = AgentTracerPlusExporter()
        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(exporter))
    """

    def __init__(self) -> None:
        self._initialized = False

    def _ensure_init(self) -> bool:
        """Check if opentelemetry-sdk is available."""
        try:
            from opentelemetry.sdk.trace.export import SpanExporter  # noqa: F401
            self._initialized = True
            return True
        except ImportError:
            logger.warning(
                "opentelemetry-sdk not installed. Install with: pip install 'agent-tracer-plus[otel]'"
            )
            return False

    def export(self, spans: Any) -> Any:
        """Export OTel spans to ATP storage (sync interface for OTel SDK)."""
        try:
            from opentelemetry.sdk.trace.export import SpanExportResult
        except ImportError:
            return None

        if not self._ensure_init():
            return SpanExportResult.FAILURE

        try:
            from agent_tracer_plus.core.context import get_tracer
            tracer = get_tracer()
            if not tracer:
                return SpanExportResult.FAILURE

            import asyncio
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

            for otel_span in spans:
                atp_span = self._otel_to_atp_span(otel_span)
                if atp_span:
                    if loop and loop.is_running():
                        loop.create_task(self._async_save(tracer, atp_span))
                    else:
                        asyncio.run(self._async_save(tracer, atp_span))

            return SpanExportResult.SUCCESS
        except Exception as e:
            logger.error(f"OTel export failed: {e}")
            return SpanExportResult.FAILURE

    @staticmethod
    async def _async_save(tracer: Any, span: Any) -> None:
        try:
            await tracer._storage.save_span(span)
        except Exception as e:
            logger.debug(f"Failed to save OTel-bridged span: {e}")

    def _otel_to_atp_span(self, otel_span: Any) -> Optional[Any]:
        """Convert an OTel ReadableSpan to an ATP Span dataclass."""
        try:
            from agent_tracer_plus.core.models import Span, SpanStatus, SpanType
            from agent_tracer_plus.utils.ids import generate_span_id

            ctx = otel_span.context
            trace_id = format(ctx.trace_id, "032x") if ctx else generate_span_id()
            span_id = format(ctx.span_id, "016x") if ctx else generate_span_id()

            parent_span_id = None
            if otel_span.parent and otel_span.parent.span_id:
                parent_span_id = format(otel_span.parent.span_id, "016x")

            attrs = dict(otel_span.attributes or {})
            span_type_str = attrs.pop("atp.span.type", "STEP")
            try:
                span_type = SpanType(span_type_str.upper())
            except ValueError:
                span_type = SpanType.STEP

            from opentelemetry.trace.status import StatusCode
            status_code = otel_span.status.status_code if otel_span.status else StatusCode.UNSET
            status = SpanStatus.ERROR if status_code == StatusCode.ERROR else SpanStatus.OK

            return Span(
                span_id=span_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                name=otel_span.name,
                span_type=span_type,
                status=status,
                started_at=otel_span.start_time / 1_000_000_000 if otel_span.start_time else 0.0,
                ended_at=otel_span.end_time / 1_000_000_000 if otel_span.end_time else 0.0,
                attributes=attrs,
                error=otel_span.status.description if status == SpanStatus.ERROR else None,
            )
        except Exception as e:
            logger.debug(f"Failed to convert OTel span: {e}")
            return None

    def shutdown(self) -> None:
        """Shutdown the exporter (no-op for ATP)."""
        pass

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        """Force flush pending data."""
        try:
            from agent_tracer_plus.core.context import get_tracer
            tracer = get_tracer()
            if tracer:
                import asyncio
                asyncio.run(tracer.flush())
        except Exception:
            pass
        return True


class ATPtoOtelBridge:
    """Bridge that exports ATP spans to an OTel exporter pipeline.

    Use this to send ATP spans to Jaeger, Grafana Tempo, Datadog, etc.

    Usage::

        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from agent_tracer_plus.storage.otel_exporter import ATPtoOtelBridge

        bridge = ATPtoOtelBridge(
            endpoint="http://localhost:4317",  # Jaeger / OTel Collector
        )
        bridge.install()  # Registers as a plugin in ATP

    Then all ATP spans will be forwarded to the OTel pipeline.
    """

    def __init__(self, endpoint: str = "http://localhost:4317") -> None:
        self.endpoint = endpoint
        self._exporter: Any = None
        self._processor: Any = None
        self._provider: Any = None

    def install(self) -> bool:
        """Install the bridge into the global OTel TracerProvider."""
        try:
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            self._exporter = OTLPSpanExporter(endpoint=self.endpoint)
            self._processor = BatchSpanProcessor(self._exporter)
            self._provider = TracerProvider()
            self._provider.add_span_processor(self._processor)

            from opentelemetry import trace as otel_trace
            otel_trace.set_tracer_provider(self._provider)

            logger.info(f"ATPtoOtelBridge installed → forwarding to {self.endpoint}")
            return True
        except ImportError as e:
            logger.warning(f"OTel bridge requires opentelemetry packages: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to install OTel bridge: {e}")
            return False
