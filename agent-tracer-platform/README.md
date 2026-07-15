# Horus / Agent Tracer Platform 🏢

The enterprise backend for the Horus ecosystem, designed to handle high-throughput telemetry ingestion, storage, and orchestration for autonomous agents.

## Architecture

This platform uses a hyper-scale pipeline configured via Docker Compose:

- **PostgreSQL**: Relational store for authentication, projects, and configuration.
- **ClickHouse**: Columnar database for scalable storage and querying of billions of agent traces.
- **Apache Kafka (KRaft)**: High-throughput ingestion buffer.
- **Qdrant**: Vector database for semantic clustering of traces and hallucination detection.
- **Redis**: Caching, pub/sub, and Chaos Monkey configuration.
- **Rust Edge Proxy (V3)**: High-performance gRPC/HTTP ingestion proxy.
- **Web API & Dashboard**: Control plane for managing agents and visualizing traces.
- **Background Workers**: Bulk processors for moving data from Kafka to ClickHouse.

## Getting Started

### Prerequisites
- Docker and Docker Compose (v3.8+)

### Running Locally

To spin up the entire platform locally:

```bash
docker-compose up -d
```

This will start all the necessary services.

### Services and Ports
- **Web API / Dashboard**: `http://localhost:3000`
- **Edge Proxy**: `http://localhost:3001` (gRPC: `50051`)
- **ClickHouse**: `http://localhost:8123` (TCP: `9000`)
- **PostgreSQL**: `localhost:5432`
- **Qdrant**: `http://localhost:6333`
- **Kafka**: `localhost:9092`
- **Redis**: `localhost:6379`

## Development

The platform consists of several core components:
- `apps/proxy`: Rust/Axum-based edge ingestion proxy.
- `api` & `worker`: Control plane and background workers.
- `alembic`: Database migrations for PostgreSQL.
- `proto`: gRPC protobuf definitions for telemetry ingestion.
- `helm`: Helm charts for Kubernetes deployment.

## Testing

To run end-to-end tests:
```bash
pytest test_e2e.py
```
