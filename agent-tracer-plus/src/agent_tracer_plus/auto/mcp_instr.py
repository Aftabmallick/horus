"""MCP (Model Context Protocol) auto-instrumentor.

Patches MCP server/client calls to automatically capture tool invocations
as TOOL spans with full request/response context. MCP is the emerging
standard protocol for tool use across Anthropic, Google, and OpenAI agents.

Supports:
- MCP Python SDK (mcp package)
- FastMCP server framework
- Both sync and async tool handlers
"""

from __future__ import annotations

import functools
import logging
from typing import Any

logger = logging.getLogger(__name__)

_PATCHED = False


def patch_mcp() -> None:
    """Patch the MCP SDK to auto-trace tool calls."""
    global _PATCHED
    if _PATCHED:
        return

    try:
        _patch_mcp_client()
        _patch_fastmcp()
    except Exception as e:
        logger.debug(f"MCP patching failed (non-fatal): {e}")
        return

    _PATCHED = True
    logger.debug("MCP SDK patched for auto-tracing")


def _patch_mcp_client() -> None:
    """Patch the MCP client's call_tool method."""
    try:
        import mcp.client.session as session_mod
        from agent_tracer_plus.core.context import SpanContext
        from agent_tracer_plus.core.models import SpanType
        from agent_tracer_plus.utils.serialization import safe_serialize

        original_call_tool = session_mod.ClientSession.call_tool

        @functools.wraps(original_call_tool)
        async def _traced_call_tool(
            self: Any, name: str, arguments: dict | None = None, **kwargs: Any
        ) -> Any:
            span_name = f"mcp.tool.{name}"
            with SpanContext(name=span_name, span_type=SpanType.TOOL) as span:
                span.set_attribute("mcp.tool.name", name)
                span.set_attribute("mcp.transport", getattr(self, "_transport_type", "unknown"))
                span.input = safe_serialize({"tool": name, "arguments": arguments or {}})

                try:
                    result = await original_call_tool(self, name, arguments, **kwargs)
                    # Extract content from MCP result
                    if hasattr(result, "content"):
                        content = [
                            getattr(c, "text", str(c))
                            for c in (result.content or [])
                            if hasattr(c, "text") or isinstance(c, str)
                        ]
                        span.set_output(safe_serialize({"content": content}))
                    span.set_attribute("mcp.is_error", getattr(result, "isError", False))
                    return result
                except Exception as e:
                    span.set_error(e)
                    raise

        session_mod.ClientSession.call_tool = _traced_call_tool
        logger.debug("Patched mcp.client.session.ClientSession.call_tool")
    except (ImportError, AttributeError) as e:
        logger.debug(f"mcp.client.session not available: {e}")


def _patch_fastmcp() -> None:
    """Patch FastMCP server tool decorators to trace server-side tool execution."""
    try:
        import fastmcp as fastmcp_mod
        from agent_tracer_plus.core.context import SpanContext
        from agent_tracer_plus.core.models import SpanType
        from agent_tracer_plus.utils.serialization import safe_serialize

        original_tool = fastmcp_mod.FastMCP.tool

        def _traced_tool_decorator(self: Any, *args: Any, **kwargs: Any) -> Any:
            """Wrap FastMCP's @tool decorator to add tracing."""
            original_decorator = original_tool(self, *args, **kwargs)

            def wrapper(func: Any) -> Any:
                tool_name = kwargs.get("name") or (args[0] if args else func.__name__)

                if hasattr(func, "__wrapped__"):
                    # Already wrapped
                    return original_decorator(func)

                import asyncio
                import inspect

                if inspect.iscoroutinefunction(func):
                    @functools.wraps(func)
                    async def async_tool_wrapper(*fargs: Any, **fkwargs: Any) -> Any:
                        span_name = f"mcp.server.tool.{tool_name}"
                        with SpanContext(name=span_name, span_type=SpanType.TOOL) as span:
                            span.set_attribute("mcp.side", "server")
                            span.set_attribute("mcp.tool.name", tool_name)
                            span.input = safe_serialize({"args": fargs, "kwargs": fkwargs})
                            try:
                                result = await func(*fargs, **fkwargs)
                                span.set_output(safe_serialize(result))
                                return result
                            except Exception as e:
                                span.set_error(e)
                                raise
                    return original_decorator(async_tool_wrapper)
                else:
                    @functools.wraps(func)
                    def sync_tool_wrapper(*fargs: Any, **fkwargs: Any) -> Any:
                        span_name = f"mcp.server.tool.{tool_name}"
                        with SpanContext(name=span_name, span_type=SpanType.TOOL) as span:
                            span.set_attribute("mcp.side", "server")
                            span.set_attribute("mcp.tool.name", tool_name)
                            span.input = safe_serialize({"args": fargs, "kwargs": fkwargs})
                            try:
                                result = func(*fargs, **fkwargs)
                                span.set_output(safe_serialize(result))
                                return result
                            except Exception as e:
                                span.set_error(e)
                                raise
                    return original_decorator(sync_tool_wrapper)

            return wrapper

        fastmcp_mod.FastMCP.tool = _traced_tool_decorator
        logger.debug("Patched fastmcp.FastMCP.tool decorator")
    except (ImportError, AttributeError) as e:
        logger.debug(f"fastmcp not available: {e}")


def instrument(tracer: Any = None) -> None:
    """Entry point called by the registry."""
    patch_mcp()
