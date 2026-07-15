"""Auto-generate agent documentation from production traces."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List

from agent_tracer_plus.core.context import get_tracer

logger = logging.getLogger(__name__)


async def generate_docs(
    agent: str,
    time_range: str = "last_7d",
    format: str = "markdown",
) -> str:
    """Generate workflow documentation from production traces.

    Analyzes actual execution paths, tool usage, and performance to generate
    always-up-to-date documentation.

    Args:
        agent: Agent name to document.
        time_range: Time range to analyze.
        format: Output format — "markdown", "mermaid", or "openapi".
    """
    tracer = get_tracer()
    if not tracer:
        return f"# Agent: {agent}\n\nNo tracer initialized — cannot generate docs."

    traces = await tracer.query(limit=5000)
    agent_traces = [t for t in traces if t.get("agent_name") == agent]

    if not agent_traces:
        return f"# Agent: {agent}\n\nNo traces found for this agent."

    # Collect span data
    all_spans: List[Any] = []
    tool_usage: Dict[str, int] = defaultdict(int)
    span_types: Dict[str, int] = defaultdict(int)
    error_spans: List[Dict[str, Any]] = []
    execution_paths: List[List[str]] = []

    for t in agent_traces:
        trace_id = t.get("trace_id", "")
        if not trace_id:
            continue
        spans = await tracer.get_spans(trace_id)
        all_spans.extend(spans)
        path = []
        for s in spans:
            span_types[s.span_type.value] += 1
            path.append(s.name)
            if s.span_type.value == "TOOL":
                tool_usage[s.name] += 1
            if s.error:
                error_spans.append({"name": s.name, "error": s.error})
        execution_paths.append(path)

    # Statistics
    total = len(agent_traces)
    errors = sum(1 for t in agent_traces if t.get("status") == "ERROR")
    avg_duration = sum(t.get("duration_ms", 0) for t in agent_traces) / total
    avg_cost = sum(t.get("total_cost", 0) for t in agent_traces) / total
    avg_tokens = sum(t.get("total_tokens", 0) for t in agent_traces) / total

    if format == "mermaid":
        return _generate_mermaid(agent, execution_paths, tool_usage)
    elif format == "openapi":
        return _generate_openapi_stub(agent, tool_usage)
    else:
        return _generate_markdown(
            agent, total, errors, avg_duration, avg_cost, avg_tokens,
            tool_usage, span_types, error_spans, execution_paths,
        )


def _generate_markdown(
    agent: str,
    total: int,
    errors: int,
    avg_duration: float,
    avg_cost: float,
    avg_tokens: float,
    tool_usage: Dict[str, int],
    span_types: Dict[str, int],
    error_spans: List[Dict[str, Any]],
    execution_paths: List[List[str]],
) -> str:
    """Generate markdown documentation."""
    lines = [
        f"# Agent: {agent}",
        "",
        f"*Auto-generated from {total} production traces.*",
        "",
        "## Performance Summary",
        "",
        "| Metric | Value |",
        "|:---|:---|",
        f"| Total Executions | {total} |",
        f"| Error Rate | {round(errors / total * 100, 1)}% |",
        f"| Avg Duration | {round(avg_duration, 1)} ms |",
        f"| Avg Cost | ${round(avg_cost, 4)} |",
        f"| Avg Tokens | {int(avg_tokens)} |",
        "",
    ]

    # Tool catalog
    if tool_usage:
        lines.extend([
            "## Tool Catalog",
            "",
            "| Tool | Usage Count |",
            "|:---|:---:|",
        ])
        for tool, count in sorted(tool_usage.items(), key=lambda x: -x[1]):
            lines.append(f"| {tool} | {count} |")
        lines.append("")

    # Span type breakdown
    if span_types:
        lines.extend([
            "## Span Type Distribution",
            "",
            "| Type | Count |",
            "|:---|:---:|",
        ])
        for stype, count in sorted(span_types.items(), key=lambda x: -x[1]):
            lines.append(f"| {stype} | {count} |")
        lines.append("")

    # Common execution paths
    if execution_paths:
        # Find most common path
        path_strs = [" → ".join(p) for p in execution_paths]
        path_counts: Dict[str, int] = defaultdict(int)
        for ps in path_strs:
            path_counts[ps] += 1

        lines.extend([
            "## Common Execution Paths",
            "",
        ])
        for path, count in sorted(path_counts.items(), key=lambda x: -x[1])[:5]:
            lines.append(f"- **{count}x**: `{path}`")
        lines.append("")

    # Common failure modes
    if error_spans:
        lines.extend([
            "## Common Failure Modes",
            "",
        ])
        err_types: Dict[str, int] = defaultdict(int)
        for e in error_spans:
            err = e.get("error", {})
            key = f"{e['name']}: {err.get('type', 'Unknown')}"
            err_types[key] += 1
        for key, count in sorted(err_types.items(), key=lambda x: -x[1])[:5]:
            lines.append(f"- **{count}x** — `{key}`")
        lines.append("")

    return "\n".join(lines)


def _generate_mermaid(
    agent: str,
    execution_paths: List[List[str]],
    tool_usage: Dict[str, int],
) -> str:
    """Generate a Mermaid.js flowchart from execution paths with edge probabilities."""
    lines = ["graph TD;"]
    
    # Count transitions for probabilities
    transitions = defaultdict(int)
    node_out_degree = defaultdict(int)
    
    for path in execution_paths:
        for i in range(len(path) - 1):
            src = path[i].replace('"', "'")
            tgt = path[i + 1].replace('"', "'")
            edge = (src, tgt)
            transitions[edge] += 1
            node_out_degree[src] += 1

    # Generate weighted edges
    for (src, tgt), count in transitions.items():
        # Calculate transition probability
        total_out = node_out_degree[src]
        prob = int((count / total_out) * 100) if total_out > 0 else 0
        lines.append(f'  {src}["{src}"] -- "{prob}%" --> {tgt}["{tgt}"]')

    return "\n".join(lines)


def _generate_openapi_stub(agent: str, tool_usage: Dict[str, int]) -> str:
    """Generate an OpenAPI-like stub for agent tools."""
    import json
    spec = {
        "openapi": "3.0.0",
        "info": {"title": f"{agent} Agent API", "version": "1.0.0"},
        "paths": {},
    }
    for tool in tool_usage:
        spec["paths"][f"/{tool}"] = {
            "post": {
                "summary": f"Tool: {tool}",
                "operationId": tool,
                "responses": {"200": {"description": "Success"}},
            }
        }
    return json.dumps(spec, indent=2)
