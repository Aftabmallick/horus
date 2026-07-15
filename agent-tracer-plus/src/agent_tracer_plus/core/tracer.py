"""AgentTracerPlus — the main tracer engine.

This is the central class that orchestrates auto-instrumentation,
storage, batch processing, and context management.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from agent_tracer_plus.alerts.manager import AlertManager
from agent_tracer_plus.budget.enforcer import BudgetEnforcer
from agent_tracer_plus.core.config import TracerConfig
from agent_tracer_plus.core.context import set_tracer
from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.processing.batch import BatchProcessor
from agent_tracer_plus.storage.base import StorageBackend
from agent_tracer_plus.storage.memory import InMemoryBackend
from agent_tracer_plus.utils.logger import get_logger
from agent_tracer_plus.security.masking import PIIMasker
from agent_tracer_plus.plugins.loader import PluginLoader

logger = get_logger("core.tracer")


class AgentTracerPlus:
    """The main tracer engine.

    Usage:
        tracer = AgentTracerPlus(service_name="my-app")
        tracer.start()
        # ... your code ...
        await tracer.shutdown()

    Or via the global init():
        import agent_tracer_plus
        agent_tracer_plus.init(service_name="my-app")
    """

    def __init__(self, config: TracerConfig | None = None, **kwargs: Any) -> None:
        # Build config from kwargs if no config provided
        if config is None:
            config = TracerConfig(**{
                k: v for k, v in kwargs.items()
                if hasattr(TracerConfig, k)
            })
        self.config = config

        # Initialize storage
        self._storage = self._init_storage(config.storage)

        # Initialize batch processor
        self._batch_processor = BatchProcessor(
            storage=self._storage,
            batch_size=config.batch_size,
            flush_interval=config.flush_interval_seconds,
            max_queue_size=config.max_queue_size,
        )

        # Budget Enforcer
        self.budget_enforcer = None
        if config.budget:
            from agent_tracer_plus.budget.enforcer import TokenBudget
            if isinstance(config.budget, dict):
                budget = TokenBudget(**config.budget)
            else:
                budget = config.budget
            self.budget_enforcer = BudgetEnforcer(budget)

        # Alert Manager
        self.alert_manager = None
        if hasattr(config, "alerts") and config.alerts:
            self.alert_manager = AlertManager(config.alerts)

        # PII Masker
        self.pii_masker = None
        if getattr(config, "pii_redaction", False):
            self.pii_masker = PIIMasker()

        # Sampler
        from agent_tracer_plus.core.models import SpanStatus
        from agent_tracer_plus.processing.sampling import Sampler
        self.sampler = Sampler(
            rate=config.sampling_rate,
            conditional=lambda t: t.status == SpanStatus.ERROR
        )

        # Replay Engine
        self.replay_engine = None
        if config.replay_trace_id:
            from agent_tracer_plus.intelligence.replay import ReplayEngine
            self.replay_engine = ReplayEngine(
                trace_id=config.replay_trace_id,
                storage=self._storage,
                diverge_span_id=config.replay_diverge_span_id
            )

        # SysProfiler
        self.profiler = None
        if config.profile_modules:
            from agent_tracer_plus.core.profiler import SysProfiler
            self.profiler = SysProfiler()

        # Anomaly Detector
        self.anomaly_detector = None
        if config.anomaly_detection:
            from agent_tracer_plus.intelligence.anomaly import AnomalyDetector
            self.anomaly_detector = AnomalyDetector()

        # Hallucination Scorer (cross-encoder, run as background task)
        self.hallucination_scorer = None
        if config.hallucination_detection:
            from agent_tracer_plus.intelligence.hallucination import HallucinationScorer
            self.hallucination_scorer = HallucinationScorer(method="cross_encoder")

        # Chaos Monkey
        self.chaos_monkey = None
        if config.chaos_mode:
            try:
                from agent_tracer_plus.chaos.monkey import ChaosMonkey
                self.chaos_monkey = ChaosMonkey(redis_url=config.chaos_redis_url)
                logger.warning("ChaosMonkey initialized — fault injection is ACTIVE")
            except Exception as e:
                logger.warning(f"Could not initialize ChaosMonkey: {e}")

        # Live Tail Server
        self.stream_server = None
        if getattr(config, "live_tail", False):
            try:
                from agent_tracer_plus.streaming.websocket import TraceStreamServer
                self.stream_server = TraceStreamServer()
            except ImportError as e:
                logger.warning(f"Could not initialize Live Tail: {e}")

        # Plugin Loader
        self.plugin_loader = PluginLoader()
        # Load plugins if they are explicitly enabled or by default
        if getattr(config, "plugins_enabled", True):
            self.plugin_loader.discover_and_load(vars(config))

        self._started = False
        self._auto_patchers_applied = False

    def _init_storage(self, storage: Any) -> StorageBackend:
        """Initialize storage backend from config value and apply resilience wrapper."""
        backend: StorageBackend
        
        if storage is None:
            logger.warning("No storage backend provided. Defaulting to in-memory storage.")
            backend = InMemoryBackend()
        elif isinstance(storage, StorageBackend):
            backend = storage
        elif isinstance(storage, str):
            backend = self._storage_from_uri(storage)
        elif isinstance(storage, list):
            # Composite backend
            backends = [
                self._storage_from_uri(s) if isinstance(s, str) else s
                for s in storage
            ]
            from agent_tracer_plus.storage.composite import CompositeBackend
            backend = CompositeBackend(backends)
        else:
            logger.warning(f"Unknown storage type: {type(storage)}, using in-memory")
            backend = InMemoryBackend()

        # Wrap with Circuit Breaker for resilience if not already wrapped
        if not hasattr(backend, "_breaker") and not isinstance(backend, InMemoryBackend):
            from agent_tracer_plus.storage.resilience import CircuitBreaker
            breaker = CircuitBreaker(name=type(backend).__name__)
            
            # Create a proxy class to wrap the backend
            class ResilientBackendWrapper:
                def __init__(self, original: StorageBackend, cb: CircuitBreaker):
                    self._original = original
                    self._breaker = cb

                async def save_trace(self, trace: Trace) -> None:
                    await self._breaker.call(self._original.save_trace, trace)

                async def save_span(self, span: Span) -> None:
                    await self._breaker.call(self._original.save_span, span)

                async def save_spans_batch(self, spans: List[Span]) -> None:
                    await self._breaker.call(self._original.save_spans_batch, spans)

                async def get_trace(self, trace_id: str) -> Optional[Trace]:
                    return await self._breaker.call(self._original.get_trace, trace_id)

                async def get_spans(self, trace_id: str) -> List[Span]:
                    return await self._breaker.call(self._original.get_spans, trace_id)

                async def query_traces(self, **kwargs: Any) -> List[Dict[str, Any]]:
                    return await self._breaker.call(self._original.query_traces, **kwargs)
                    
                async def delete_traces(self, before: Any) -> int:
                    return await self._breaker.call(self._original.delete_traces, before)

                async def flush(self) -> None:
                    await self._original.flush()

                async def close(self) -> None:
                    await self._original.close()

                async def health_check(self) -> bool:
                    return await self._original.health_check()
            
            backend = ResilientBackendWrapper(backend, breaker) # type: ignore

        return backend

    @staticmethod
    def _storage_from_uri(uri: str) -> StorageBackend:
        """Create a storage backend from a URI string."""
        if uri.startswith("sqlite://"):
            from agent_tracer_plus.storage.sqlite import SQLiteBackend
            path = uri.replace("sqlite://", "")
            return SQLiteBackend(path or "./agent_traces.db")

        if uri.startswith("ndjson://") or uri.endswith(".jsonl"):
            from agent_tracer_plus.storage.ndjson import NDJSONBackend
            path = uri.replace("ndjson://", "")
            return NDJSONBackend(path or "./agent_traces")

        if uri == "memory://":
            return InMemoryBackend()

        logger.warning(f"Unknown storage URI format: {uri}. Defaulting to in-memory storage.")
        return InMemoryBackend()

    def start(self) -> None:
        """Start the tracer — begin auto-instrumentation and batch processing."""
        if self._started or not self.config.enabled:
            return

        # Set global tracer reference
        set_tracer(self)

        # Start batch processor and Live Tail
        try:
            loop = asyncio.get_running_loop()
            self._batch_processor.start(loop)
            if self.replay_engine:
                loop.create_task(self.replay_engine.load())
            if self.stream_server:
                loop.create_task(self.stream_server.start())
        except RuntimeError:
            # No running event loop — processor will use sync mode
            self._batch_processor.start(None)
            if self.replay_engine:
                asyncio.run(self.replay_engine.load())
            if self.stream_server:
                import threading
                def _start_server():
                    l = asyncio.new_event_loop()
                    asyncio.set_event_loop(l)
                    l.run_until_complete(self.stream_server.start())
                    l.run_forever()
                t = threading.Thread(target=_start_server, daemon=True)
                t.start()

        # Apply auto-instrumentation patches
        if self.config.auto_instrument and not self._auto_patchers_applied:
            self._apply_auto_patches()
            self._auto_patchers_applied = True
            
        # Start Profiler if configured
        if self.profiler:
            self.profiler.start(self.config.profile_modules)

        # Trigger plugin on_start
        self.plugin_loader.trigger_on_start(self)

        self._started = True
        logger.info(
            f"Agent Tracer Plus started (service={self.config.service_name}, "
            f"storage={type(self._storage).__name__})"
        )

    def _apply_auto_patches(self) -> None:
        """Apply monkey patches for auto-instrumentation."""
        try:
            from agent_tracer_plus.auto.patcher import AutoPatcher
            patcher = AutoPatcher(self.config)
            patcher.patch_all()
        except Exception as e:
            logger.warning(f"Auto-instrumentation failed (non-fatal): {e}")

    # ── Internal API (used by context managers and decorators) ──

    def _enqueue_trace(self, trace: Trace) -> None:
        """Enqueue a completed trace for storage."""
        if not self.config.enabled:
            return
        if not self.sampler.should_sample(trace):
            return

        if self.pii_masker:
            self.pii_masker.mask_trace(trace)

        # Budget enforcement — check BEFORE queuing; raise if on_exceed=="kill"
        if self.budget_enforcer:
            self.budget_enforcer.check_budget(trace)

        # Anomaly detection — attach anomalies to trace metadata synchronously
        if self.anomaly_detector:
            try:
                anomalies = self.anomaly_detector.detect_trace_anomalies(trace)
                if anomalies:
                    trace.metadata["anomalies"] = [
                        a if isinstance(a, dict) else vars(a) for a in anomalies
                    ]
            except Exception as e:
                logger.debug(f"Anomaly detection failed (non-fatal): {e}")

        # Hallucination scoring — async background task (non-blocking)
        if self.hallucination_scorer:
            llm_spans = [s for s in trace.spans if str(s.span_type).upper() == "LLM"]
            retrieval_spans = [s for s in trace.spans if str(s.span_type).upper() in ("RETRIEVAL", "TOOL")]
            if llm_spans and retrieval_spans:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        self._score_hallucinations_background(trace, llm_spans, retrieval_spans)
                    )
                except RuntimeError:
                    pass  # No running loop — skip background scoring

        # Alert Manager
        if self.alert_manager:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.alert_manager.process_trace(trace.to_dict()))
            except RuntimeError:
                import threading
                t = threading.Thread(
                    target=asyncio.run,
                    args=(self.alert_manager.process_trace(trace.to_dict()),),
                    daemon=True
                )
                t.start()

        # Live Tail
        if self.stream_server:
            self.stream_server.broadcast(trace.to_dict())

        # Plugins
        self.plugin_loader.trigger_on_trace_end(trace)

        self._batch_processor.enqueue_trace(trace)

    async def _score_hallucinations_background(
        self, trace: Trace, llm_spans: list, retrieval_spans: list
    ) -> None:
        """Background task: score hallucination with cross-encoder and patch span attributes."""
        if not self.hallucination_scorer:
            return
        context_text = "\n".join(
            [str(s.output) for s in retrieval_spans if s.output]
        )
        if not context_text.strip():
            return
        for span in llm_spans:
            claim = str(span.output) if span.output else ""
            if not claim.strip():
                continue
            try:
                score = await asyncio.to_thread(
                    self.hallucination_scorer.score, claim, context_text
                )
                span.set_attribute("hallucination.score", getattr(score, "score", None))
                span.set_attribute("hallucination.label", getattr(score, "label", None))
            except Exception as e:
                logger.debug(f"Hallucination scoring failed for span {span.span_id}: {e}")


    def _enqueue_span(self, span: Span) -> None:
        """Enqueue a completed span for storage."""
        if not self.config.enabled:
            return
            
        if self.pii_masker:
            self.pii_masker.mask_span(span)

        self.plugin_loader.trigger_on_span_end(span)
            
        self._batch_processor.enqueue_span(span)

    # ── Public Query API ──

    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Retrieve a trace by ID."""
        return await self._storage.get_trace(trace_id)

    async def get_spans(self, trace_id: str) -> List[Span]:
        """Retrieve all spans for a trace."""
        return await self._storage.get_spans(trace_id)

    async def query(self, limit: int = 100, offset: int = 0, **filters: Any) -> List[Dict[str, Any]]:
        """Query traces with filters."""
        return await self._storage.query_traces(filters=filters, limit=limit, offset=offset)

    # ── Lifecycle ──

    async def flush(self) -> None:
        """Force flush all pending data to storage."""
        await self._batch_processor.flush()

    async def shutdown(self) -> None:
        """Gracefully shut down the tracer."""
        if not self._started:
            return
            
        logger.info("Shutting down Agent Tracer Plus...")
        
        self.plugin_loader.trigger_on_shutdown()
        
        if self.profiler:
            self.profiler.stop()

        if self.stream_server:
            await self.stream_server.stop()
            
        await self._batch_processor.shutdown()
        self._started = False

    def check_replay(self, span_type: str, name: str, input_payload: Any) -> tuple[bool, Any]:
        """Check if execution should be mocked by the ReplayEngine."""
        if not self.replay_engine or self.replay_engine.diverged:
            return False, None
            
        # If the trace is still loading in background, we shouldn't execute
        if not getattr(self.replay_engine, "trace", None) and not self.replay_engine.diverged:
            logger.warning("ReplayEngine hasn't finished loading, falling back to live execution.")
            self.replay_engine.diverged = True
            return False, None
            
        return self.replay_engine.should_mock(span_type, name, input_payload)

    @property
    def storage(self) -> StorageBackend:
        """Access the storage backend directly."""
        return self._storage

    def get_metrics(self) -> Dict[str, Any]:
        """Return self-telemetry metrics (Observing the Observer)."""
        metrics = {
            "status": "active" if self._started else "stopped",
            "service_name": self.config.service_name,
            "batch_processor": {
                "pending_count": self._batch_processor.pending_count if hasattr(self._batch_processor, "pending_count") else 0,
            },
            "storage_backend": type(self._storage).__name__,
        }
        
        # Add circuit breaker stats if resilience wrapper is used
        if hasattr(self._storage, "_breaker"):
            metrics["storage_circuit_breaker"] = self._storage._breaker.stats()
            
        # Add live tail stats
        if self.stream_server:
            metrics["live_tail"] = {
                "client_count": self.stream_server.client_count,
                "clients": self.stream_server.get_client_stats(),
            }
            
        return metrics
