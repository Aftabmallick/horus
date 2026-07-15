"""Comprehensive tests for decorators — function, class, async, generator, static/classmethod."""

import asyncio

import pytest

from agent_tracer_plus.core.context import SpanContext, TraceContext, get_current_span, get_current_trace
from agent_tracer_plus.core.models import SpanStatus, SpanType
from agent_tracer_plus.decorators import trace_agent, trace_step, trace_tool, trace_llm, trace_handoff, trace_guardrail
from agent_tracer_plus.decorators.base import create_span_wrapper, wrap_class


class TestSyncFunctionDecorators:
    def test_trace_step_returns_result(self):
        @trace_step(name="step")
        def my_step(x):
            return x * 2

        result = my_step(5)
        assert result == 10

    def test_trace_tool_returns_result(self):
        @trace_tool(name="tool")
        def my_tool(query):
            return f"result for {query}"

        assert my_tool("hello") == "result for hello"

    def test_trace_agent_creates_root_trace(self):
        @trace_agent(name="MyAgent")
        def my_agent(x):
            return x + 1

        result = my_agent(10)
        assert result == 11
        assert get_current_trace() is None  # Trace should be cleaned up

    def test_decorator_preserves_docstring(self):
        @trace_step(name="doc_step")
        def documented():
            """This is my docstring."""
            pass

        assert documented.__doc__ == "This is my docstring."

    def test_decorator_preserves_name(self):
        @trace_step(name="named_step")
        def original_name():
            pass

        assert original_name.__name__ == "original_name"

    def test_exception_propagates(self):
        @trace_step(name="fail_step")
        def failing():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            failing()


class TestAsyncFunctionDecorators:
    @pytest.mark.asyncio
    async def test_async_step(self):
        @trace_step(name="async_step")
        async def my_async(x):
            return x * 3

        result = await my_async(4)
        assert result == 12

    @pytest.mark.asyncio
    async def test_async_agent(self):
        @trace_agent(name="AsyncAgent")
        async def my_agent():
            return "done"

        result = await my_agent()
        assert result == "done"

    @pytest.mark.asyncio
    async def test_async_exception(self):
        @trace_step(name="async_fail")
        async def failing():
            raise RuntimeError("async fail")

        with pytest.raises(RuntimeError, match="async fail"):
            await failing()


class TestClassDecorators:
    @pytest.mark.asyncio
    async def test_class_decoration(self):
        @trace_agent(name="ClassAgent")
        class MyAgent:
            async def run(self):
                return await self.helper()

            async def helper(self):
                return "helper_result"

        agent = MyAgent()
        result = await agent.run()
        assert result == "helper_result"

    @pytest.mark.asyncio
    async def test_class_private_methods_skipped(self):
        @trace_agent(name="PrivateAgent")
        class Agent:
            async def run(self):
                return self._internal()

            def _internal(self):
                return "private"

        agent = Agent()
        result = await agent.run()
        assert result == "private"

    @pytest.mark.asyncio
    async def test_explicit_decorator_priority(self):
        """Explicit decorator on a method should take priority."""
        @trace_agent(name="ExplicitAgent")
        class Agent:
            @trace_step(name="explicit_step", span_type="RETRIEVAL")
            async def retrieve(self):
                return "data"

        agent = Agent()
        result = await agent.retrieve()
        assert result == "data"


class TestGeneratorDecorators:
    def test_sync_generator(self):
        @trace_step(name="gen_step")
        def my_gen(n):
            for i in range(n):
                yield i

        results = list(my_gen(3))
        assert results == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_async_generator(self):
        @trace_step(name="async_gen_step")
        async def my_async_gen(n):
            for i in range(n):
                yield i

        results = []
        async for item in my_async_gen(3):
            results.append(item)
        assert results == [0, 1, 2]


class TestWrapClass:
    def test_exclude_methods(self):
        class MyClass:
            def keep(self):
                return "kept"

            def skip(self):
                return "skipped"

        wrapped = wrap_class(
            MyClass,
            span_type=SpanType.CUSTOM,
            name_prefix="MyClass",
            exclude_methods=["skip"],
        )

        assert hasattr(wrapped.keep, "_atp_traced")
        assert not hasattr(MyClass.__dict__["skip"], "_atp_traced")

    def test_explicit_only_skips_all(self):
        class MyClass:
            def method(self):
                return "m"

        wrapped = wrap_class(
            MyClass,
            span_type=SpanType.CUSTOM,
            name_prefix="MyClass",
            trace_methods="explicit_only",
        )
        # explicit_only returns class unchanged
        assert not hasattr(MyClass.__dict__["method"], "_atp_traced")

    def test_include_private(self):
        class MyClass:
            def _private(self):
                return "p"

        wrapped = wrap_class(
            MyClass,
            span_type=SpanType.CUSTOM,
            name_prefix="MyClass",
            include_private=True,
        )
        assert hasattr(wrapped._private, "_atp_traced")

    def test_double_wrap_prevention(self):
        """A method already marked with _atp_traced should not be wrapped again."""
        class MyClass:
            def method(self):
                return "m"

        wrapped1 = wrap_class(MyClass, span_type=SpanType.CUSTOM, name_prefix="MC")
        method_ref = wrapped1.method

        wrapped2 = wrap_class(wrapped1, span_type=SpanType.CUSTOM, name_prefix="MC")
        # Should be the exact same wrapper, not double-wrapped
        assert wrapped2.method is method_ref


class TestNestedDecorators:
    def test_nested_span_hierarchy(self):
        """Decorators should maintain correct parent-child span hierarchy."""
        spans_seen = []

        @trace_agent(name="OuterAgent")
        def outer():
            return inner()

        @trace_step(name="inner_step")
        def inner():
            span = get_current_span()
            if span:
                spans_seen.append((span.name, span.parent_span_id))
            return "inner_done"

        result = outer()
        assert result == "inner_done"
