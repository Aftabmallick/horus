---
sidebar_position: 4
---

# REST API Reference

The Agent Tracer Platform exposes a FastAPI backend (`/api/v1`) that handles trace ingestion, UI queries, and prompt versioning.

## Traces
### `POST /api/v1/traces`
Ingest a new trace or update an existing one.
- **Request Body**: JSON containing `trace_id`, `agent_name`, and a list of `spans`.
- **Response**: `200 OK`

### `GET /api/v1/traces`
Retrieve a paginated list of traces.
- **Query Params**: `limit`, `offset`, `tenant_id`.
- **Response**: JSON array of Trace objects.

### `GET /api/v1/traces/{trace_id}`
Retrieve detailed span and Directed Acyclic Graph (DAG) data for a specific trace.
- **Response**: Detailed Trace object including `spans` array.

## Prompts & Versioning
### `POST /api/v1/prompts`
Create a new prompt template or a new branch.
- **Request Body**: `name`, `template_string`, `branch`, `parent_id`.

### `GET /api/v1/prompts`
Retrieve all prompts and their lineage (branches).

## Evaluation & Scoring
### `POST /api/v1/scores`
Attach a human or automated evaluation score to a specific trace or span.
- **Request Body**: `trace_id`, `span_id`, `score_name`, `score_value`.

## High-Throughput Streaming
### `WS /api/v1/stream/live`
WebSocket endpoint for the Live Firehose. Yields JSON trace headers instantly upon ingestion for real-time visualization.
