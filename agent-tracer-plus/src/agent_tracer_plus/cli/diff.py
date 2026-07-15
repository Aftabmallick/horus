import sys
import argparse
import asyncio
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from agent_tracer_plus import AgentTracerPlus, TracerConfig
from agent_tracer_plus.intelligence.diff import diff_traces, SpanDiff

console = Console()

async def async_run_diff(trace_a: str, trace_b: str, storage_uri: str) -> None:
    # We just need the storage, so initialize tracer without starting workers
    config = TracerConfig(storage=storage_uri, enabled=False)
    tracer = AgentTracerPlus(config)
    
    storage = tracer._storage
    
    t_a = await storage.get_trace(trace_a)
    t_b = await storage.get_trace(trace_b)
    
    if not t_a:
        console.print(f"[red]Error: Trace {trace_a} not found in {storage_uri}[/red]")
        sys.exit(1)
    if not t_b:
        console.print(f"[red]Error: Trace {trace_b} not found in {storage_uri}[/red]")
        sys.exit(1)
        
    s_a = await storage.get_spans(trace_a)
    s_b = await storage.get_spans(trace_b)
    
    report = diff_traces(t_a, s_a, t_b, s_b)
    
    console.print(f"\n[bold]=== Trace Diff: {trace_a} -> {trace_b} ===[/bold]")
    
    # Stats
    stats_table = Table(show_header=False, box=None)
    stats_table.add_row("Duration:", f"{'+' if report.duration_delta_ms > 0 else ''}{report.duration_delta_ms:.2f}ms")
    stats_table.add_row("Tokens:", f"{'+' if report.token_delta > 0 else ''}{report.token_delta}")
    stats_table.add_row("Cost:", f"{'+$' if report.cost_delta > 0 else '-$'}{abs(report.cost_delta):.4f}")
    console.print(Panel(stats_table, title="Stats", border_style="blue", expand=False))
    
    # Reasoning Path
    console.print("\n[bold]Reasoning Path:[/bold]")
    for op in report.span_ops:
        if op.opcode == "equal":
            prefix, style = "=", "white"
            name = op.base_span.name
            type_str = op.base_span.span_type.value
        elif op.opcode == "replace":
            prefix, style = "~", "yellow"
            name = op.compare_span.name
            type_str = op.compare_span.span_type.value
        elif op.opcode == "insert":
            prefix, style = "+", "green"
            name = op.compare_span.name
            type_str = op.compare_span.span_type.value
        elif op.opcode == "delete":
            prefix, style = "-", "red"
            name = op.base_span.name
            type_str = op.base_span.span_type.value
            
        console.print(f"[{style}]{prefix} \\[{type_str}] {name}[/{style}]")
        
    # Deep Changes
    console.print("\n[bold]Deep Changes:[/bold]")
    found_changes = False
    for op in report.span_ops:
        if op.opcode in ("replace", "equal"):
            span_name = op.compare_span.name if op.compare_span else op.base_span.name
            if op.input_changed and op.input_diff:
                console.print(f"\n[bold yellow]Input changed in `{span_name}`:[/bold yellow]")
                # Print unified diff properly
                for line in op.input_diff.splitlines():
                    if line.startswith("+"):
                        console.print(f"[green]{line}[/green]")
                    elif line.startswith("-"):
                        console.print(f"[red]{line}[/red]")
                    elif line.startswith("@"):
                        console.print(f"[cyan]{line}[/cyan]")
                    else:
                        console.print(line)
                found_changes = True
                
            if op.output_changed and op.output_diff:
                console.print(f"\n[bold yellow]Output changed in `{span_name}`:[/bold yellow]")
                for line in op.output_diff.splitlines():
                    if line.startswith("+"):
                        console.print(f"[green]{line}[/green]")
                    elif line.startswith("-"):
                        console.print(f"[red]{line}[/red]")
                    elif line.startswith("@"):
                        console.print(f"[cyan]{line}[/cyan]")
                    else:
                        console.print(line)
                found_changes = True
                
    if not found_changes:
        console.print("[dim]No string-level input/output changes found in matched spans.[/dim]")


def run_diff(args: argparse.Namespace) -> None:
    asyncio.run(async_run_diff(args.trace_a, args.trace_b, args.storage))
