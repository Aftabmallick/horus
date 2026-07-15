import sys
import argparse
import asyncio
from typing import List

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from agent_tracer_plus import AgentTracerPlus, TracerConfig
from agent_tracer_plus.intelligence.anomaly import AnomalyDetector
from agent_tracer_plus.core.models import Trace

console = Console()

async def async_run_anomalies(trace_id: str, storage_uri: str, window_size: int = 100) -> None:
    config = TracerConfig(storage=storage_uri, enabled=False)
    tracer = AgentTracerPlus(config)
    storage = tracer._storage
    
    target_trace = await storage.get_trace(trace_id)
    if not target_trace:
        console.print(f"[red]Error: Trace {trace_id} not found in {storage_uri}[/red]")
        sys.exit(1)
        
    target_spans = await storage.get_spans(trace_id)
    
    # Fetch historical traces for the same agent
    console.print(f"[dim]Fetching historical baseline for agent `{target_trace.agent_name}`...[/dim]")
    # Get all traces for this agent. Note: in a real implementation we would want a query that limits and sorts by time.
    # For now, we will fetch all and sort.
    all_traces = await storage.query_traces(limit=window_size * 2) 
    history_traces = [t for t in all_traces if t.agent_name == target_trace.agent_name and t.trace_id != trace_id]
    history_traces.sort(key=lambda t: t.started_at)
    
    # We just need the last window_size traces
    if len(history_traces) > window_size:
        history_traces = history_traces[-window_size:]
        
    if len(history_traces) < 5:
        console.print(f"[yellow]Warning: Only found {len(history_traces)} historical traces for agent `{target_trace.agent_name}`. Anomaly detection requires at least 5 traces to build a baseline.[/yellow]")
        sys.exit(0)
        
    history_spans_list = []
    for t in history_traces:
        spans = await storage.get_spans(t.trace_id)
        history_spans_list.append(spans)
        
    detector = AnomalyDetector(history_traces, history_spans_list, window_size=window_size)
    anomalies = detector.detect(target_trace, target_spans)
    
    console.print(f"\n[bold]=== Anomaly Report: {trace_id} ===[/bold]")
    console.print(f"Agent: {target_trace.agent_name} (Compared against last {len(history_traces)} runs)\n")
    
    if not anomalies:
        console.print("[green]✅ No anomalies detected in this trace.[/green]")
        return
        
    for anomaly in anomalies:
        if anomaly["severity"] == "high":
            color = "red"
            icon = "🔴 [HIGH]"
        else:
            color = "yellow"
            icon = "🟡 [MEDIUM]"
            
        console.print(f"[{color}]{icon} {anomaly['type'].replace('_', ' ').title()} ({anomaly['level'].title()} Level)[/{color}]")
        console.print(f"   {anomaly['message']}\n")


def run_anomalies(args: argparse.Namespace) -> None:
    asyncio.run(async_run_anomalies(args.trace_id, args.storage, args.window))
