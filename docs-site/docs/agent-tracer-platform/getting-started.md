---
sidebar_position: 1
---

# Platform Overview

The Agent Tracer Platform provides an enterprise-grade UI and API layer for visualizing, debugging, and managing agent executions at hyper-scale.

## Architecture Components

1. **FastAPI Backend (`/api/v1`)**: A high-performance Python ASGI application that ingests traces and serves UI queries.
2. **React Flow UI**: A dynamic, rich-aesthetic frontend that visualizes traces as Directed Acyclic Graphs (DAGs) and provides Time-Travel Replay debugging.
3. **Data Layer**: Backed by PostgreSQL (relational metadata), ClickHouse (analytical metrics), and Redis (pub/sub and circuit breaking).

## Quick Start (Docker Compose)

The easiest way to start the platform locally is via Docker Compose.

```bash
git clone https://github.com/your-org/agent-tracer-platform.git
cd agent-tracer-platform

# Spin up the API, UI, and Database dependencies
docker-compose up --build
```
Once the containers are healthy, open your browser to `http://localhost:5173` to view the dashboard!

## Enterprise Kubernetes Deployment

For production, we provide a robust Helm chart:

```bash
helm upgrade --install agent-tracer helm/agent-tracer \
  -f helm/agent-tracer/values.yaml \
  --namespace observability --create-namespace
```

## Features

- **Pro Mode (High Density)**: Toggle the UI to strip padding and reduce font sizes for reading massive JSON context payloads quickly.
- **Prompt Branching**: Test experimental prompt chains side-by-side with production chains using our dual-pane A/B testing playground.
- **Live Firehose**: Watch traces stream in real-time at 1000+ RPS without browser lag.
