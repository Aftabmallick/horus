"""Auto-instrumentation for gRPC."""

import logging

from agent_tracer_plus import current_trace
from agent_tracer_plus.core.tracer import AgentTracerPlus
from agent_tracer_plus.propagation.w3c import extract_context, inject_context

logger = logging.getLogger(__name__)


def instrument(tracer: AgentTracerPlus) -> None:
    """Instrument gRPC via interceptors."""
    try:
        import grpc
    except ImportError:
        logger.debug("grpcio not found, skipping instrumentation.")
        return

    # A more robust implementation would inject Client/Server interceptors globally.
    # For now, this is a placeholder that exposes interceptor classes users can attach.

    class TracingClientInterceptor(grpc.UnaryUnaryClientInterceptor):
        def intercept_unary_unary(self, continuation, client_call_details, request):
            metadata = []
            if client_call_details.metadata:
                metadata = list(client_call_details.metadata)

            headers = inject_context({})
            for k, v in headers.items():
                metadata.append((k, v))

            new_details = client_call_details._replace(metadata=metadata)

            trace = current_trace()
            span = trace.span(f"grpc.call.{client_call_details.method}", span_type="STEP")
            with span:
                return continuation(new_details, request)

    class TracingServerInterceptor(grpc.ServerInterceptor):
        def intercept_service(self, continuation, handler_call_details):
            headers = dict(handler_call_details.invocation_metadata)
            ctx = extract_context(headers)

            trace = current_trace()
            if ctx:
                trace = trace.continue_from(ctx, name=f"grpc.serve.{handler_call_details.method}")
            else:
                trace.span(f"grpc.serve.{handler_call_details.method}", span_type="STEP").__enter__()

            try:
                return continuation(handler_call_details)
            finally:
                if trace.current_span:
                    trace.current_span.__exit__(None, None, None)

    # Expose interceptors in module
    globals()['TracingClientInterceptor'] = TracingClientInterceptor
    globals()['TracingServerInterceptor'] = TracingServerInterceptor

    logger.debug("Successfully instrumented gRPC (interceptors available).")
