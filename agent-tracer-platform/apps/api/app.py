"""FastAPI server for the Agent Tracer Plus dashboard."""

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

try:
    from prometheus_client import make_asgi_app, Counter, Histogram
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

from apps.api.routes import router
from agent_tracer_plus.core.context import get_tracer
from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from apps.api.platform_db import platform_db
    from agent_tracer_plus import init
    from aiokafka import AIOKafkaProducer
    
    logger.info("Initializing Agent Tracer Plus Server...")
    # Initialize the Platform DB (Auth/Multitenancy)
    await platform_db.init_pool()
    
    # Initialize the underlying trace storage
    ch_url = os.getenv("CLICKHOUSE_URL")
    if ch_url:
        from agent_tracer_plus.storage.clickhouse import ClickHouseStorage
        import urllib.parse
        parsed = urllib.parse.urlparse(ch_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8123
        username = parsed.username or "default"
        password = parsed.password or ""
        
        logger.info(f"Using ClickHouse backend for traces: {host}:{port}")
        storage = ClickHouseStorage(host=host, port=port, username=username, password=password)
        app.state.tracer = init(service_name="agent-tracer-server", storage=storage)
    else:
        logger.info("Using SQLite backend for traces.")
        if not os.getenv("AGENT_TRACER_DISABLE_SERVER_TRACING"):
            app.state.tracer = init(service_name="agent-tracer-server")
            
    tracer = getattr(app.state, "tracer", None)
    if tracer:
        logger.info(f"Dashboard connected to storage: {type(tracer.storage).__name__}")
    else:
        logger.warning("No active tracer found! Ensure agent_tracer_plus.init() is called before starting the UI.")
    
    # Initialize Kafka Producer
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)
    await producer.start()
    app.state.kafka_producer = producer
    logger.info(f"Kafka Producer started on {bootstrap_servers}")

    yield
    
    # Shutdown logic
    logger.info("Shutting down services...")
    if hasattr(app.state, "kafka_producer"):
        await app.state.kafka_producer.stop()
        logger.info("Kafka Producer stopped.")
    
    await platform_db.close_pool()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Agent Tracer Plus Dashboard",
        description="Observability UI and APIs for Agent Tracer Plus",
        version="0.1.0",
        lifespan=lifespan
    )

    # CORS — configurable via env var for production hardening
    _raw_origins = os.getenv("ALLOWED_ORIGINS", "")
    if _raw_origins:
        _allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
    else:
        _allowed_origins = ["*"]

    _env = os.getenv("ENVIRONMENT", "development")
    if _env == "production" and "*" in _allowed_origins:
        logger.warning(
            "SECURITY WARNING: CORS allow_origins=['*'] in production. "
            "Set ALLOWED_ORIGINS env var to restrict access (e.g. 'https://app.example.com')."
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # API routes (versioned)
    app.include_router(router, prefix="/api/v1")

    # Prometheus metrics
    if HAS_PROMETHEUS:
        metrics_app = make_asgi_app()
        app.mount("/metrics", metrics_app)
        logger.info("Prometheus metrics exposed at /metrics")

    # Serve built static UI if it exists
    # The UI will be built to `apps/ui/dist`
    dist_dir = os.path.join(os.path.dirname(__file__), "..", "ui", "dist")
    dist_dir = os.path.abspath(dist_dir)
            
    if os.path.exists(dist_dir):
        app.mount("/", StaticFiles(directory=dist_dir, html=True), name="ui")
    else:
        logger.warning(f"UI dist directory not found at {dist_dir}. API is running, but UI will not be served.")

    return app


app = create_app()
