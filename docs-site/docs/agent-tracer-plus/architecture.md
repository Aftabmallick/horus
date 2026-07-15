---
sidebar_position: 2
---

# Architecture

Agent Tracer Plus was redesigned from the ground up to support Hyper-Scale multi-agent topologies, seamlessly matching the ingestion speeds of enterprise tools like LangSmith and Arize Phoenix.

## Core Data Model
At the heart of the tracer are two primary OpenTelemetry-aligned models: `Trace` and `Span`.

- **Trace**: Represents an entire execution lifecycle (e.g., a user's prompt traversing multiple agents, databases, and guardrails).
- **Span**: A specific unit of work within a trace (e.g., an LLM call, a tool execution). Spans form a Directed Acyclic Graph (DAG) through parent-child ID relationships.

### OpenTelemetry (OTLP) Native
Our models natively serialize to the OTLP Protobuf JSON format. By eliminating intermediate middleware, Agent Tracer Plus achieves zero-latency serialization for streaming data to the UI.

## Storage Backends

Agent Tracer Plus supports a completely modular `StorageBackend` interface.

### Synchronous / Lightweight
- **MemoryBackend**: For unit tests and short-lived scripts.
- **SQLiteBackend**: For local development.
- **NDJSONBackend**: For logging traces to disk.

### High-Throughput / Enterprise
- **ClickHouseStorage**: Ideal for high-scale analytical queries over millions of spans.
- **RedisStreamStorage**: Perfect for event-driven real-time pipelines.
- **KafkaStorage**: For massive parallel ingestion and durability.
- **MongoDBStorage**: For flexible JSON document storage.

## Async Context Propagation
Traces are automatically propagated across asynchronous boundaries (e.g., `asyncio.gather`, ThreadPools) using `contextvars`. You do not need to manually pass a `trace_id` down your call stack.
