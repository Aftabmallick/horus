import pytest
from agent_tracer_plus import trace_agent, init
from agent_tracer_plus.core.context import get_tracer

def test_decorator_inheritance_traces_child_methods():
    tracer = init(storage="memory://", force=True)
    
    class Parent:
        def parent_method(self):
            return "parent"
            
    @trace_agent(name="ChildAgent")
    class Child(Parent):
        def child_method(self):
            return "child"
            
    c = Child()
    assert c.child_method() == "child"
    assert c.parent_method() == "parent"
    
    import asyncio
    asyncio.run(tracer.flush())
    
    # Both should be traced
    spans = tracer.storage.get_all_spans()
    
    names = [s["name"] for s in spans]
    assert "ChildAgent.child_method" in names
    assert "ChildAgent.parent_method" in names
