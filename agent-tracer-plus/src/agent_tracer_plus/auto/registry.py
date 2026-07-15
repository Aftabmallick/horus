"""Instrumentor registry — dynamic discovery of installed packages for auto-instrumentation.

Each instrumentor registers itself with a target module name and a patch function.
The AutoPatcher queries this registry to apply only the patches for installed packages.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class InstrumentorEntry:
    """A registered instrumentor."""

    name: str
    target_module: str  # e.g. "openai", "langchain", "crewai"
    patch_fn: Callable[[], None]
    config_flag: str = ""  # e.g. "instrument_openai"
    priority: int = 100  # Lower = higher priority (LLM patches before HTTP)
    description: str = ""
    patched: bool = field(default=False, init=False)


class InstrumentorRegistry:
    """Central registry for all auto-instrumentors.

    Usage:
        registry = InstrumentorRegistry()
        registry.register("openai", "openai", patch_openai, config_flag="instrument_openai")
        registry.apply_all(config)
    """

    def __init__(self) -> None:
        self._entries: Dict[str, InstrumentorEntry] = {}

    def register(
        self,
        name: str,
        target_module: str,
        patch_fn: Callable[[], None],
        config_flag: str = "",
        priority: int = 100,
        description: str = "",
    ) -> None:
        """Register an instrumentor."""
        self._entries[name] = InstrumentorEntry(
            name=name,
            target_module=target_module,
            patch_fn=patch_fn,
            config_flag=config_flag,
            priority=priority,
            description=description,
        )

    def unregister(self, name: str) -> None:
        """Remove an instrumentor from the registry."""
        self._entries.pop(name, None)

    def get(self, name: str) -> Optional[InstrumentorEntry]:
        """Get an instrumentor entry by name."""
        return self._entries.get(name)

    @property
    def entries(self) -> List[InstrumentorEntry]:
        """Get all entries sorted by priority."""
        return sorted(self._entries.values(), key=lambda e: e.priority)

    def is_installed(self, module_name: str) -> bool:
        """Check if a Python package is importable."""
        try:
            importlib.import_module(module_name)
            return True
        except ImportError:
            return False

    def apply_all(self, config: Any = None) -> List[str]:
        """Apply all applicable patches.

        Args:
            config: TracerConfig instance. If a config_flag is set on the entry,
                    the corresponding config attribute must be True.

        Returns:
            List of successfully patched module names.
        """
        patched: List[str] = []

        for entry in self.entries:
            # Check config flag
            if entry.config_flag and config is not None:
                if not getattr(config, entry.config_flag, True):
                    logger.debug(f"Skipping {entry.name}: disabled by config ({entry.config_flag}=False)")
                    continue

            # Check if target module is installed
            if not self.is_installed(entry.target_module):
                logger.debug(f"Skipping {entry.name}: {entry.target_module} not installed")
                continue

            # Apply patch
            try:
                entry.patch_fn()
                entry.patched = True
                patched.append(entry.name)
                logger.debug(f"Patched {entry.name} ({entry.target_module})")
            except Exception as e:
                logger.warning(f"Failed to patch {entry.name}: {e}")

        if patched:
            logger.info(f"Auto-instrumented: {', '.join(patched)}")
        else:
            logger.debug("No auto-instrumentable packages detected")

        return patched


# ── Global default registry with all built-in instrumentors ──


def _build_default_registry() -> InstrumentorRegistry:
    """Build the default registry with all built-in instrumentors."""
    registry = InstrumentorRegistry()

    # Phase 1: LLM providers (highest priority)
    registry.register(
        name="openai",
        target_module="openai",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.openai_instr", fromlist=["patch_openai"]).patch_openai(),
        config_flag="instrument_openai",
        priority=10,
        description="OpenAI SDK auto-capture (completions, embeddings, images)",
    )
    registry.register(
        name="anthropic",
        target_module="anthropic",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.anthropic_instr", fromlist=["patch_anthropic"]).patch_anthropic(),
        config_flag="instrument_anthropic",
        priority=10,
        description="Anthropic SDK auto-capture (messages, completions)",
    )
    registry.register(
        name="google_genai",
        target_module="google.genai",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.google_genai_instr", fromlist=["instrument"]).instrument(None),
        priority=15,
        description="Google GenAI SDK auto-capture (generate_content)",
    )

    # Phase 2: Frameworks
    # Note: langchain/llama_index/celery/grpc/db use instrument(tracer) pattern.
    # We pass None as tracer — each instrumentor handles its own imports internally.
    registry.register(
        name="langchain",
        target_module="langchain",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.langchain_instr", fromlist=["instrument"]).instrument(None),
        config_flag="instrument_langchain",
        priority=20,
        description="LangChain callback handler installation",
    )
    registry.register(
        name="llama_index",
        target_module="llama_index",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.llama_index_instr", fromlist=["instrument"]).instrument(None),
        priority=20,
        description="LlamaIndex callback handler installation",
    )
    registry.register(
        name="crewai",
        target_module="crewai",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.crewai_instr", fromlist=["patch_crewai"]).patch_crewai(),
        priority=20,
        description="CrewAI agent/task/crew auto-capture",
    )
    registry.register(
        name="autogen",
        target_module="autogen",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.autogen_instr", fromlist=["patch_autogen"]).patch_autogen(),
        priority=20,
        description="AutoGen conversable agent auto-capture",
    )
    registry.register(
        name="agno",
        target_module="agno",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.agno_instr", fromlist=["patch_agno"]).patch_agno(),
        priority=20,
        description="Agno framework agent/LLM auto-capture",
    )
    registry.register(
        name="mcp",
        target_module="mcp",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.mcp_instr", fromlist=["instrument"]).instrument(None),
        priority=22,
        description="MCP (Model Context Protocol) client/server tool call auto-capture",
    )
    registry.register(
        name="fastmcp",
        target_module="fastmcp",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.mcp_instr", fromlist=["instrument"]).instrument(None),
        priority=22,
        description="FastMCP server @tool decorator auto-capture",
    )

    # Phase 3: HTTP (important for distributed tracing)
    registry.register(
        name="httpx",
        target_module="httpx",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.http_instr", fromlist=["patch_httpx"]).patch_httpx(),
        config_flag="instrument_http",
        priority=30,
        description="httpx HTTP client with W3C header injection",
    )
    registry.register(
        name="requests",
        target_module="requests",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.http_instr", fromlist=["patch_requests"]).patch_requests(),
        config_flag="instrument_http",
        priority=30,
        description="requests HTTP client with W3C header injection",
    )
    registry.register(
        name="aiohttp",
        target_module="aiohttp",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.http_instr", fromlist=["patch_aiohttp"]).patch_aiohttp(),
        config_flag="instrument_http",
        priority=30,
        description="aiohttp async HTTP client with W3C header injection",
    )

    # Phase 4: Infrastructure
    registry.register(
        name="celery",
        target_module="celery",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.celery_instr", fromlist=["instrument"]).instrument(None),
        priority=40,
        description="Celery task dispatch and execution tracing",
    )
    registry.register(
        name="grpc",
        target_module="grpc",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.grpc_instr", fromlist=["instrument"]).instrument(None),
        priority=40,
        description="gRPC client/server interceptors",
    )
    registry.register(
        name="psycopg2",
        target_module="psycopg2",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.db_instr", fromlist=["instrument"]).instrument(None),
        priority=50,
        description="PostgreSQL query tracing",
    )
    registry.register(
        name="redis",
        target_module="redis",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.db_instr", fromlist=["instrument"]).instrument(None),
        priority=50,
        description="Redis command tracing",
    )
    registry.register(
        name="kafka",
        target_module="aiokafka",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.kafka_instr", fromlist=["instrument"]).instrument(None),
        priority=40,
        description="Kafka producer/consumer tracing",
    )
    registry.register(
        name="websockets",
        target_module="websockets",
        patch_fn=lambda: __import__("agent_tracer_plus.auto.websocket_instr", fromlist=["instrument"]).instrument(None),
        priority=40,
        description="WebSocket send/receive tracing",
    )

    return registry


# Singleton
default_registry = _build_default_registry()
