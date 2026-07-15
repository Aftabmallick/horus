"""Configuration management for Agent Tracer Plus."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TracerConfig:
    """Configuration for the AgentTracerPlus tracer.

    All fields have sensible defaults — the tracer works with zero config.
    """

    # Identity
    service_name: str = "default"
    service_instance_id: str = ""
    tenant_id: str = ""

    # Storage
    storage: Any = None  # StorageBackend instance or connection string
    archive: Optional[str] = None  # Archive backend (e.g., S3 URI)

    # Distributed tracing
    propagator: str = "w3c"  # "w3c" | "b3" | "none"

    # Sampling
    sampling_rate: float = 1.0  # 0.0 to 1.0

    # Processing
    batch_size: int = 100  # Flush after N items
    flush_interval_seconds: float = 5.0  # Flush every N seconds
    max_queue_size: int = 10_000  # Max items in queue before dropping

    # Data capture
    capture_input: bool = True
    capture_output: bool = True
    max_input_size: int = 10_000  # Max chars for input capture
    max_output_size: int = 10_000  # Max chars for output capture

    # Token/cost tracking
    track_tokens: bool = True
    track_cost: bool = True
    custom_pricing: Dict[str, Any] = field(default_factory=dict)

    # Auto-instrumentation
    auto_instrument: bool = True
    profile_modules: List[str] = field(default_factory=list)
    instrument_openai: bool = True
    instrument_anthropic: bool = True
    instrument_http: bool = True
    instrument_langchain: bool = True

    # Enterprise features (Phase 3)
    encryption_key: Optional[str] = None
    pii_redaction: bool = False
    retention_days: int = 90
    
    # Global Budget Settings (or pass TokenBudget to `budget` field)
    budget: Any = None  # TokenBudget or dict
    max_tokens_per_minute: Optional[int] = None
    max_cost_per_minute: Optional[float] = None
    
    # Intelligence Layer (Phase 2)
    anomaly_detection: bool = False
    hallucination_detection: bool = False
    carbon_tracking: bool = False
    memory_tracing: bool = False
    chaos_mode: bool = False

    # Streaming / Plugin (Phase 4)
    live_tail: bool = False
    plugins_enabled: bool = True

    # Chaos Engineering (Phase 5)
    chaos_redis_url: str = "redis://localhost:6379/0"

    # A/B Experiments (Phase 5)
    ab_experiment: Optional[str] = None  # Experiment name to auto-tag all spans

    # Alert configuration
    alerts: Any = None  # AlertConfig or dict

    # Time-Travel Replay
    replay_trace_id: Optional[str] = None
    replay_diverge_span_id: Optional[str] = None

    # Debug
    debug: bool = False
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TracerConfig:
        """Create config from a dictionary, ignoring unknown keys."""
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    @classmethod
    def from_env(cls) -> TracerConfig:
        """Create config from environment variables."""
        import os

        config = cls()
        env_map = {
            "AGENT_TRACER_PLUS_SERVICE_NAME": "service_name",
            "AGENT_TRACER_PLUS_TENANT_ID": "tenant_id",
            "AGENT_TRACER_PLUS_STORAGE": "storage",
            "AGENT_TRACER_PLUS_SAMPLING_RATE": "sampling_rate",
            "AGENT_TRACER_PLUS_ENABLED": "enabled",
            "AGENT_TRACER_PLUS_DEBUG": "debug",
        }

        for env_key, attr in env_map.items():
            value = os.environ.get(env_key)
            if value is not None:
                # Type coercion
                current = getattr(config, attr)
                if isinstance(current, bool):
                    setattr(config, attr, value.lower() in ("1", "true", "yes"))
                elif isinstance(current, float):
                    setattr(config, attr, float(value))
                elif isinstance(current, int):
                    setattr(config, attr, int(value))
                else:
                    setattr(config, attr, value)

        return config
