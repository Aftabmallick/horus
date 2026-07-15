"""Auto-instrumentation for Databases."""

import logging
from functools import wraps

from agent_tracer_plus import current_trace
from agent_tracer_plus.core.tracer import AgentTracerPlus
from agent_tracer_plus.core.models import SpanType

logger = logging.getLogger(__name__)


def instrument(tracer: AgentTracerPlus) -> None:
    """Instrument database drivers like psycopg2 and asyncpg."""
    try:
        from agent_tracer_plus.auto.patcher import wrap
    except ImportError:
        return

    # Psycopg2
    try:
        import psycopg2.extensions

        def trace_execute(func):
            @wraps(func)
            def wrapper(self, query, vars=None):
                trace = current_trace()
                span = trace.span("db.query", span_type=SpanType.DATABASE)
                span.set_attribute("db.system", "postgresql")
                span.set_attribute("db.statement", query)
                if vars:
                    span.set_attribute("db.params_count", len(vars) if isinstance(vars, (list, tuple, dict)) else 1)
                
                with span:
                    try:
                        res = func(self, query, vars)
                        if hasattr(self, "rowcount") and self.rowcount >= 0:
                            span.set_attribute("db.row_count", self.rowcount)
                        return res
                    except Exception as e:
                        span.set_error(e)
                        raise
            return wrapper

        wrap(psycopg2.extensions.cursor, "execute", trace_execute(psycopg2.extensions.cursor.execute))
        logger.debug("Successfully instrumented psycopg2.")
    except ImportError:
        pass

    # Asyncpg
    try:
        import asyncpg.connection

        def trace_async_execute(func):
            @wraps(func)
            async def wrapper(self, query, *args, **kwargs):
                trace = current_trace()
                span = trace.span("db.query", span_type=SpanType.DATABASE)
                span.set_attribute("db.system", "postgresql")
                span.set_attribute("db.statement", query)
                if args:
                    span.set_attribute("db.params_count", len(args))
                    
                with span:
                    try:
                        res = await func(self, query, *args, **kwargs)
                        if isinstance(res, str) and res.startswith(("SELECT", "INSERT", "UPDATE", "DELETE")):
                            span.set_attribute("db.operation_result", res)
                        elif isinstance(res, list):
                            span.set_attribute("db.row_count", len(res))
                        return res
                    except Exception as e:
                        span.set_error(e)
                        raise
            return wrapper

        wrap(asyncpg.connection.Connection, "execute", trace_async_execute(asyncpg.connection.Connection.execute))
        wrap(asyncpg.connection.Connection, "fetch", trace_async_execute(asyncpg.connection.Connection.fetch))
        logger.debug("Successfully instrumented asyncpg.")
    except ImportError:
        pass

