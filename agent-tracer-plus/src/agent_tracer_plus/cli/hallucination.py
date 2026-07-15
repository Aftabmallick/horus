import sys
import argparse
import asyncio

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from agent_tracer_plus import AgentTracerPlus, TracerConfig
from agent_tracer_plus.intelligence.hallucination import detect_hallucination, LLMJudgeEngine, CrossEncoderEngine

console = Console()

async def async_run_hallucination(trace_id: str, storage_uri: str, engine_type: str) -> None:
    config = TracerConfig(storage=storage_uri, enabled=False)
    tracer = AgentTracerPlus(config)
    storage = tracer._storage
    
    target_trace = await storage.get_trace(trace_id)
    if not target_trace:
        console.print(f"[red]Error: Trace {trace_id} not found in {storage_uri}[/red]")
        sys.exit(1)
        
    target_spans = await storage.get_spans(trace_id)
    
    console.print(f"[dim]Scanning trace `{trace_id}` for LLM hallucinations using {engine_type} engine...[/dim]")
    
    if engine_type == "cross-encoder":
        engine = CrossEncoderEngine()
    else:
        engine = LLMJudgeEngine()
        
    scores = await detect_hallucination(target_trace, target_spans, engine)
    
    console.print(f"\n[bold]=== Hallucination Report: {trace_id} ===[/bold]")
    console.print(f"Engine: {engine_type.title()}\n")
    
    if not scores:
        console.print("[dim]No LLM spans found to evaluate, or no preceding context found.[/dim]")
        return
        
    for score in scores:
        span = next((s for s in target_spans if s.span_id == score.span_id), None)
        span_name = span.name if span else score.span_id
        
        if score.error:
            if "No prior context" in score.error:
                console.print(f"[dim]Span `{span_name}` skipped (No prior context to verify against)[/dim]")
            else:
                console.print(f"[red]Error evaluating span `{span_name}`: {score.error}[/red]")
            continue
            
        if score.score >= 0.8:
            color = "green"
            icon = "✅"
        elif score.score >= 0.4:
            color = "yellow"
            icon = "🟡"
        else:
            color = "red"
            icon = "🔴"
            
        console.print(f"[{color}]{icon} Span `{span_name}` Faithfulness Score: {score.score:.2f}[/{color}]")
        
        if score.claims:
            console.print("   [bold]Claims Analysis:[/bold]")
            for i, claim in enumerate(score.claims, 1):
                c_icon = "✅" if claim.entailed else "❌"
                c_color = "green" if claim.entailed else "red"
                status = "Entailed" if claim.entailed else "Hallucination"
                console.print(f"   [{c_color}]{c_icon} Claim {i}: {claim.claim} ({status})[/{c_color}]")
                if not claim.entailed and claim.reason:
                    console.print(f"      [dim]Reason: {claim.reason}[/dim]")
        console.print("")


def run_hallucination(args: argparse.Namespace) -> None:
    asyncio.run(async_run_hallucination(args.trace_id, args.storage, args.engine))
