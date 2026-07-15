import sys
import argparse
import asyncio

from rich.console import Console
from agent_tracer_plus import AgentTracerPlus, TracerConfig
from agent_tracer_plus.testing.generator import generate_pytest_file

console = Console()

async def async_run_generate_tests(trace_id: str, storage_uri: str, output_dir: str) -> None:
    config = TracerConfig(storage=storage_uri, enabled=False)
    tracer = AgentTracerPlus(config)
    storage = tracer._storage
    
    trace = await storage.get_trace(trace_id)
    if not trace:
        console.print(f"[red]Error: Trace {trace_id} not found in {storage_uri}[/red]")
        sys.exit(1)
        
    spans = await storage.get_spans(trace_id)
    
    file_path = generate_pytest_file(trace, spans, output_dir)
    console.print(f"[green]✅ Generated pytest file: {file_path}[/green]")

def run_generate_tests(args: argparse.Namespace) -> None:
    asyncio.run(async_run_generate_tests(args.trace_id, args.storage, args.output))
