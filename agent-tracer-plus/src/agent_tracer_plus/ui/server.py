"""Embedded UI server for Agent Tracer Plus."""

import os
import functools
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from agent_tracer_plus.core.tracer import AgentTracerPlus
from agent_tracer_plus.storage.base import StorageBackend

app = FastAPI(title="Agent Tracer Plus - Local UI")

# Attempt to mount static files if the directory exists
STATIC_DIR = Path(__file__).parent / "static"


@functools.lru_cache(maxsize=1)
def get_storage() -> StorageBackend:
    """Instantiate the storage backend based on environment."""
    uri = os.environ.get("AGENT_TRACER_PLUS_UI_STORAGE", "memory://")
    # Tracer has a handy _storage_from_uri static method
    return AgentTracerPlus._storage_from_uri(uri)


@app.get("/")
async def serve_index() -> HTMLResponse:
    """Serve the zero-build React HTML dashboard."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html not found in static folder.")
    return HTMLResponse(content=index_file.read_text(), status_code=200)


@app.get("/api/traces")
async def list_traces(limit: int = 50) -> Dict[str, Any]:
    """Get the most recent traces."""
    storage = get_storage()
    traces = await storage.query_traces(limit=limit)
    
    # query_traces returns list of dicts directly
    return {"traces": traces}


@app.get("/api/traces/{trace_id}")
async def get_trace_detail(trace_id: str) -> Dict[str, Any]:
    """Get full details of a specific trace, including all spans."""
    storage = get_storage()
    trace = await storage.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
        
    spans = await storage.get_spans(trace_id)
    
    # Sort chronologically
    spans = sorted(spans, key=lambda s: s.started_at)
    
    return {
        "trace": trace.to_dict(),
        "spans": [s.to_dict() for s in spans]
    }
