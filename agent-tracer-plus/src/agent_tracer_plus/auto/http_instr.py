"""HTTP client auto-instrumentation with W3C Trace Context header injection."""

from __future__ import annotations

import functools
from typing import Any

from agent_tracer_plus.core.context import SpanContext, get_current_span, get_current_trace
from agent_tracer_plus.core.models import SpanType
from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("auto.http")
_HTTPX_PATCHED = False
_REQUESTS_PATCHED = False

def _inject_trace_headers(headers: dict) -> dict:
    """Inject W3C traceparent header into outgoing HTTP headers."""
    trace = get_current_trace()
    span = get_current_span()
    if trace and span:
        clean_trace_id = trace.trace_id.replace("-", "")[:32].ljust(32, "0")
        clean_span_id = span.span_id.replace("-", "")[:16].ljust(16, "0")
        traceparent = f"00-{clean_trace_id}-{clean_span_id}-01"
        headers["traceparent"] = traceparent
    return headers

def patch_httpx() -> None:
    global _HTTPX_PATCHED
    if _HTTPX_PATCHED:
        return
    try:
        import httpx
        orig_send = httpx.Client.send
        orig_async_send = httpx.AsyncClient.send

        @functools.wraps(orig_send)
        def traced_send(self: Any, request: Any, *args: Any, **kwargs: Any) -> Any:
            trace = get_current_trace()
            span_obj = get_current_span()
            if trace and span_obj:
                clean_trace_id = trace.trace_id.replace("-", "")[:32].ljust(32, "0")
                clean_span_id = span_obj.span_id.replace("-", "")[:16].ljust(16, "0")
                traceparent = f"00-{clean_trace_id}-{clean_span_id}-01"
                request.headers["traceparent"] = traceparent
            method = request.method
            url = str(request.url)
            with SpanContext(name=f"HTTP {method} {url}", span_type=SpanType.RPC) as span:
                span.set_attribute("http.method", method)
                span.set_attribute("http.url", url)
                try:
                    response = orig_send(self, request, *args, **kwargs)
                    span.set_attribute("http.status_code", response.status_code)
                    return response
                except Exception as e:
                    span.set_error(e)
                    raise

        @functools.wraps(orig_async_send)
        async def traced_async_send(self: Any, request: Any, *args: Any, **kwargs: Any) -> Any:
            trace = get_current_trace()
            span_obj = get_current_span()
            if trace and span_obj:
                clean_trace_id = trace.trace_id.replace("-", "")[:32].ljust(32, "0")
                clean_span_id = span_obj.span_id.replace("-", "")[:16].ljust(16, "0")
                traceparent = f"00-{clean_trace_id}-{clean_span_id}-01"
                request.headers["traceparent"] = traceparent
            method = request.method
            url = str(request.url)
            with SpanContext(name=f"HTTP {method} {url}", span_type=SpanType.RPC) as span:
                span.set_attribute("http.method", method)
                span.set_attribute("http.url", url)
                try:
                    response = await orig_async_send(self, request, *args, **kwargs)
                    span.set_attribute("http.status_code", response.status_code)
                    return response
                except Exception as e:
                    span.set_error(e)
                    raise

        httpx.Client.send = traced_send
        httpx.AsyncClient.send = traced_async_send
        _HTTPX_PATCHED = True
        logger.debug("httpx patched successfully")
    except Exception as e:
        logger.warning(f"Failed to patch httpx: {e}")

def patch_requests() -> None:
    global _REQUESTS_PATCHED
    if _REQUESTS_PATCHED:
        return
    try:
        import requests
        orig_request = requests.Session.request

        @functools.wraps(orig_request)
        def traced_request(self: Any, method: str, url: str, **kwargs: Any) -> Any:
            headers = kwargs.get("headers", {}) or {}
            _inject_trace_headers(headers)
            kwargs["headers"] = headers
            with SpanContext(name=f"HTTP {method.upper()} {url}", span_type=SpanType.RPC) as span:
                span.set_attribute("http.method", method.upper())
                span.set_attribute("http.url", url)
                try:
                    response = orig_request(self, method, url, **kwargs)
                    span.set_attribute("http.status_code", response.status_code)
                    return response
                except Exception as e:
                    span.set_error(e)
                    raise

        requests.Session.request = traced_request
        _REQUESTS_PATCHED = True
        logger.debug("requests patched successfully")
    except Exception as e:
        logger.warning(f"Failed to patch requests: {e}")

_AIOHTTP_PATCHED = False

def patch_aiohttp() -> None:
    global _AIOHTTP_PATCHED
    if _AIOHTTP_PATCHED:
        return
    try:
        import aiohttp
        orig_request = aiohttp.ClientSession._request

        @functools.wraps(orig_request)
        async def traced_aiohttp_request(self: Any, method: str, url: str, **kwargs: Any) -> Any:
            headers = kwargs.pop("headers", {}) or {}
            _inject_trace_headers(headers)
            kwargs["headers"] = headers
            with SpanContext(name=f"HTTP {method.upper()} {url}", span_type=SpanType.RPC) as span:
                span.set_attribute("http.method", method.upper())
                span.set_attribute("http.url", str(url))
                try:
                    response = await orig_request(self, method, url, **kwargs)
                    span.set_attribute("http.status_code", response.status)
                    return response
                except Exception as e:
                    span.set_error(e)
                    raise

        aiohttp.ClientSession._request = traced_aiohttp_request
        _AIOHTTP_PATCHED = True
        logger.debug("aiohttp patched successfully")
    except Exception as e:
        logger.warning(f"Failed to patch aiohttp: {e}")
