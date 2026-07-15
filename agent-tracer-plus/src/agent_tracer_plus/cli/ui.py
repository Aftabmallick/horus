"""CLI 'ui' command — launches the embedded local dashboard."""

import os
import sys
import threading
import time
import webbrowser

from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("cli.ui")

def run_ui(port: int = 8000, storage_uri: str = "sqlite://./agent_traces.db") -> None:
    """Run the FastAPI embedded UI via Uvicorn."""
    try:
        import fastapi
        import uvicorn
    except ImportError:
        logger.error(
            "The 'ui' extra dependencies are not installed. "
            "Please install them via: pip install 'agent-tracer-plus[ui]'"
        )
        sys.exit(1)
        
    os.environ["AGENT_TRACER_PLUS_UI_STORAGE"] = storage_uri

    # Define a thread to open the browser after a short delay
    def open_browser():
        time.sleep(1.5)
        url = f"http://localhost:{port}"
        logger.info(f"Opening browser to {url}")
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()

    logger.info(f"Starting embedded UI on port {port} (Storage: {storage_uri})")
    
    # Run uvicorn programmatically
    # We pass the import string instead of the app instance so auto-reload works if we wanted it
    uvicorn.run("agent_tracer_plus.ui.server:app", host="127.0.0.1", port=port, log_level="warning")
