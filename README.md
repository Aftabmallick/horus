# Horus 👁️

Horus is a comprehensive observability and tracing ecosystem designed for autonomous AI agents, RAG pipelines, and LLM applications. 

It provides end-to-end visibility, from a lightweight zero-code instrumentation library up to a hyper-scale telemetry ingestion platform.

## Ecosystem Components

This workspace contains the following core components:

### 1. [Agent Tracer Plus](./agent-tracer-plus)
The python-based library/SDK for capturing agent traces. It auto-instruments your code (OpenAI, Anthropic, HTTP, MCP tools) with zero code changes required. It can export traces to various backends or directly to the Horus Platform.
- **Key Features**: Zero-code auto-instrumentation, token/cost budgets, PII redaction, and an OpenTelemetry native exporter.

### 2. [Agent Tracer Platform](./agent-tracer-platform)
The enterprise backend and control plane for the Horus ecosystem.
- **Architecture**: A hyper-scale ingestion pipeline powered by Kafka, ClickHouse, PostgreSQL, Qdrant, and Redis. It provides a web dashboard and APIs for managing telemetry at scale.

### 3. [Docs Site](./docs-site)
The Docusaurus-based documentation website for the Horus ecosystem.

## Getting Started

To get started, explore the individual components:

- **Want to trace your Python agents?** Check out the [Agent Tracer Plus README](file:///Users/aftabmallick/Desktop/horus/agent-tracer-plus/README.md).
- **Want to spin up the enterprise backend?** Check out the [Platform README](file:///Users/aftabmallick/Desktop/horus/agent-tracer-platform/README.md).
- **Want to run the documentation locally?** Check out the [Docs README](file:///Users/aftabmallick/Desktop/horus/docs-site/README.md).

## License

This project is licensed under the MIT License. See the individual subdirectories for specific licensing details.
