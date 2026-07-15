"""Initialization file for Agent Tracer Plus."""

from agent_tracer_plus.core.context import get_tracer, get_current_trace as current_trace, get_current_span as current_span, SpanContext as trace_block
from agent_tracer_plus.core.tracer import AgentTracerPlus
from agent_tracer_plus.decorators import (
    trace_agent, trace_step, trace_tool, trace_llm,
    trace_handoff, trace_guardrail, trace_mcp,
    trace_memory, trace_workflow, trace_routing, trace_policy
)

# Global tracer instance (used by get_tracer)
_tracer = None

__all__ = [
    "AgentTracerPlus", "init", "show",
    "get_tracer", "current_trace", "current_span", "trace_block",
    "trace_agent", "trace_step", "trace_tool", "trace_llm",
    "trace_handoff", "trace_guardrail", "trace_mcp",
    "trace_memory", "trace_workflow", "trace_routing", "trace_policy"
]


def init(**kwargs) -> AgentTracerPlus:
    """Initialize the global tracer instance."""
    global _tracer
    tracer = AgentTracerPlus(**kwargs)
    tracer.start()
    _tracer = tracer
    return tracer


def show(limit: int = 1) -> None:
    """Developer helper: pretty-print the most recent traces to the console."""
    import asyncio
    import json
    import sys
    from datetime import datetime

    tracer = get_tracer()
    if not tracer:
        print("⚠️ Agent Tracer Plus is not initialized.")
        return

    async def _fetch() -> None:
        traces = await tracer.query(limit=limit)
        if not traces:
            print("📭 No traces found.")
            return

        for i, t in enumerate(traces):
            trace_id = t.get("trace_id", "unknown")
            status = t.get("status", "UNKNOWN")
            agent = t.get("agent_name", "unnamed-agent")
            
            # Format time
            started = t.get("started_at", 0)
            if isinstance(started, (int, float)):
                time_str = datetime.fromtimestamp(started).strftime("%H:%M:%S")
            else:
                time_str = str(started)[:19]

            print(f"\n[{i+1}/{len(traces)}] 🔍 Trace: {trace_id} ({time_str})")
            print(f"├─ Agent:  {agent}")
            print(f"├─ Status: {status}")
            
            # Print cost/tokens if available
            cost = t.get("total_cost", 0.0)
            tokens = t.get("total_tokens", 0)
            if cost > 0 or tokens > 0:
                print(f"├─ Usage:  ${cost:.4f} / {tokens} tokens")

            # Fetch and print span tree
            spans = await tracer.get_spans(trace_id)
            if not spans:
                print("└─ (No spans recorded)")
                continue

            print("└─ Execution Tree:")
            
            # Simple tree rendering (assumes sorted by time)
            sorted_spans = sorted(spans, key=lambda s: s.started_at or 0)
            
            # Map parent IDs to children for indentation
            children_map = {}
            for s in sorted_spans:
                parent = s.parent_span_id
                if parent not in children_map:
                    children_map[parent] = []
                children_map[parent].append(s)

            def print_node(span_id, level=1):
                if span_id not in children_map:
                    return
                for s in children_map[span_id]:
                    indent = "    " * level
                    s_type = str(s.span_type).split(".")[-1]
                    s_name = s.name
                    s_status = str(s.status).split(".")[-1]
                    
                    # Duration
                    try:
                        dur_ms = ((s.ended_at or 0) - (s.started_at or 0)) * 1000
                    except TypeError:
                        dur_ms = 0.0
                    dur_str = f"[{dur_ms:.1f}ms]"
                    
                    # Indicator
                    indicator = "🔴" if s_status == "ERROR" else ("🟡" if s_type == "LLM" else "🔵")
                    
                    print(f"{indent}{indicator} {s_name} {dur_str}")
                    
                    # If LLM, show prompt/completion summary
                    if s_type == "LLM":
                        try:
                            inp = json.loads(s.input) if isinstance(s.input, str) else s.input
                            out = json.loads(s.output) if isinstance(s.output, str) else s.output
                            model = s.attributes.get("gen_ai.request.model", "unknown")
                            print(f"{indent}    └─ model: {model}")
                        except Exception:
                            pass
                    
                    print_node(s.span_id, level + 1)

            # Start with root spans (no parent)
            print_node(None, 1)
            print("")

    # Run the async fetch synchronously for console UX
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_fetch())
    except RuntimeError:
        asyncio.run(_fetch())
