"""AI Root Cause Analysis for traces."""

import json
from typing import Any, Dict

from agent_tracer_plus.core.models import Span, SpanStatus, Trace
from agent_tracer_plus.graph.builder import DependencyGraph
from agent_tracer_plus.search.semantic import SemanticSearcher
from agent_tracer_plus.core.context import get_tracer


class TraceDiagnoser:
    """Uses an LLM to diagnose failures within a trace tree."""

    SYSTEM_PROMPT = (
        "You are an expert AI debugging assistant. I will provide you with a trace "
        "of an autonomous agent's execution, structured as an execution DAG (Directed Acyclic Graph). "
        "Your job is to identify the root cause of any failure, "
        "explain exactly where the agent went wrong, and suggest a fix.\n\n"
        "If past successful fixes are provided via RAG, heavily weigh them in your diagnosis.\n"
        "Focus on hallucinated tools, bad prompt instructions, or context window overflow."
    )

    def __init__(self, api_key: str = "", model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model

    def _format_trace_for_llm(self, trace: Trace, spans: list[Span]) -> str:
        """Compress the trace into a readable format for the LLM using DAG topology."""
        lines = []
        lines.append(f"Trace ID: {trace.trace_id} (Status: {trace.status.value})")
        lines.append(f"Agent Name: {trace.agent_name}")

        # Build DAG for contextualization
        dag = DependencyGraph()
        for s in spans:
            dag.add_node(s.name, node_type=s.span_type.value)
            if s.parent_span_id:
                parent = next((p for p in spans if p.span_id == s.parent_span_id), None)
                if parent:
                    dag.add_edge(parent.name, s.name)
                    
        lines.append("\nExecution Topology (DAG):")
        
        # Output paths through the tree
        try:
            if hasattr(dag, 'get_critical_paths'):
                paths = dag.get_critical_paths()
                if paths:
                    lines.append(f"Critical Path: {' -> '.join(paths[0])}")
        except Exception:
            pass

        # Sort chronologically for detailed view
        sorted_spans = sorted(spans, key=lambda s: s.started_at)

        for i, span in enumerate(sorted_spans):
            lines.append(f"\n[{i+1}] Span: {span.name} (Type: {span.span_type.value}, Status: {span.status.value})")

            if span.input:
                inp_str = json.dumps(span.input)
                # Truncate if too long
                if len(inp_str) > 1000:
                    inp_str = inp_str[:1000] + "... [truncated]"
                lines.append(f"  Input: {inp_str}")

            if span.output:
                out_str = json.dumps(span.output)
                if len(out_str) > 1000:
                    out_str = out_str[:1000] + "... [truncated]"
                lines.append(f"  Output: {out_str}")

            if span.error:
                lines.append(f"  ERROR: {span.error}")

        return "\n".join(lines)

    async def _fetch_historical_fixes(self, error_msg: str) -> str:
        """RAG for historical fixes using semantic search."""
        if not error_msg:
            return ""
            
        tracer = get_tracer()
        if not tracer:
            return ""
            
        searcher = SemanticSearcher()
        await searcher.build_index()
        
        # Search for similar errors
        results = await searcher.search(query=f"error: {error_msg}", top_k=3)
        if not results:
            return ""
            
        fixes = []
        for r in results:
            trace = r.get("trace", {})
            # Only include traces that eventually succeeded or were fixed
            if trace.get("status") == "OK":
                fixes.append(f"- Found successful trace dealing with similar context: {r.get('text_snippet', '')[:200]}")
                
        if fixes:
            return "\n\nPAST SUCCESSFUL FIXES (RAG Context):\n" + "\n".join(fixes)
        return ""

    async def diagnose(self, trace: Trace, spans: list[Span]) -> Dict[str, Any]:
        """Diagnose a trace using LiteLLM."""
        if trace.status != SpanStatus.ERROR and not any(s.status == SpanStatus.ERROR for s in spans):
            return {"status": "ok", "diagnosis": "Trace execution was successful. No errors found."}

        trace_text = self._format_trace_for_llm(trace, spans)
        
        # Get main error message for RAG
        error_msg = next((s.error for s in spans if s.error), None)
        rag_context = await self._fetch_historical_fixes(error_msg) if error_msg else ""
        
        prompt_content = f"Please analyze this trace:\n\n{trace_text}"
        if rag_context:
            prompt_content += rag_context

        try:
            import litellm
        except ImportError:
            raise ImportError("litellm is required for trace diagnosis. Install with `pip install litellm`.")

        response = await litellm.acompletion(
            model=self.model,
            api_key=self.api_key if self.api_key else None,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt_content}
            ]
        )

        diagnosis_text = response.choices[0].message.content
        return {
            "status": "diagnosed",
            "diagnosis": diagnosis_text,
            "analyzed_spans": len(spans)
        }
