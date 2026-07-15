"""CLI Tail Command for real-time trace streaming."""

import asyncio
from datetime import datetime

from agent_tracer_plus import init
from agent_tracer_plus.core.context import get_tracer

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
GRAY = "\033[90m"


def print_trace(trace: dict):
    """Format and print a trace event."""
    ts = datetime.fromisoformat(trace.get("started_at", datetime.now().isoformat())).strftime("%H:%M:%S.%f")[:-3]

    status = trace.get("status", "RUNNING")
    if status == "ERROR":
        status_color = RED
    elif status == "OK" or status == "COMPLETED":
        status_color = GREEN
    else:
        status_color = YELLOW

    agent = trace.get("agent_name", "UnknownAgent")
    tid = trace.get("trace_id", "")[:8]

    cost = trace.get("total_cost", 0.0)
    cost_str = f"${cost:.4f}" if cost > 0 else ""
    tokens = trace.get("total_tokens", 0)
    tok_str = f"{tokens}tk" if tokens > 0 else ""

    metrics = f"{GRAY}{tok_str} {cost_str}{RESET}"

    print(f"{GRAY}[{ts}]{RESET} {status_color}{BOLD}{status:8}{RESET} {MAGENTA}{tid}{RESET} {CYAN}{agent}{RESET} {metrics}")


async def tail_traces(service_name: str = None, filter_str: str = None):
    """Continuously poll and print new traces from the active storage backend."""
    # Assume default sqlite if nothing is initialized
    if not get_tracer():
        init(service_name=service_name or "tail-client")

    tracer = get_tracer()
    print(f"{BOLD}Streaming traces from {type(tracer.storage).__name__}...{RESET} (Press Ctrl+C to quit)")

    # Simple polling mechanism (in production, use LISTEN/NOTIFY for Postgres or Websockets)
    seen_ids = set()

    # Pre-warm seen list to avoid dumping entire DB on start
    try:
        initial_traces = await tracer.query(limit=50)
        for t in initial_traces:
            seen_ids.add(t.get("trace_id"))
    except Exception:
        pass

    try:
        while True:
            try:
                # Query newest traces
                traces = await tracer.query(limit=20)

                # We need to print them in chronological order
                new_traces = []
                for t in traces:
                    if t.get("trace_id") not in seen_ids:
                        new_traces.append(t)
                        seen_ids.add(t.get("trace_id"))

                # Sort by started_at
                new_traces.sort(key=lambda x: x.get("started_at", ""))

                for t in new_traces:
                    # Basic filtering
                    if filter_str:
                        # e.g., filter_str "status=error"
                        if "=" in filter_str:
                            k, v = filter_str.split("=", 1)
                            if str(t.get(k, "")).lower() != v.lower():
                                continue

                    print_trace(t)
            except Exception:
                pass

            await asyncio.sleep(1.0)
    except asyncio.CancelledError:
        pass


def run_tail(service: str, filter_str: str):
    try:
        asyncio.run(tail_traces(service, filter_str))
    except KeyboardInterrupt:
        print(f"\n{GRAY}Live tail stopped.{RESET}")
