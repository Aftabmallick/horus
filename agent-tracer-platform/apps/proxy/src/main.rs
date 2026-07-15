use axum::{
    extract::State,
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    routing::post,
    Json, Router,
};
use rskafka::client::{
    ClientBuilder,
    partition::{PartitionClient, UnknownTopicHandling, Compression},
};
use rskafka::record::Record;
use serde_json::Value;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{error, info};
use chrono::Utc;

#[derive(Clone)]
struct AppState {
    trace_producer: Arc<PartitionClient>,
    span_producer: Arc<PartitionClient>,
    // Basic in-memory cache for API keys
    key_cache: Arc<RwLock<std::collections::HashMap<String, String>>>,
}

async fn validate_key(headers: &HeaderMap, state: &AppState) -> Result<String, StatusCode> {
    let auth = headers.get("authorization").and_then(|h| h.to_str().ok());
    let pub_key = headers.get("x-public-key").and_then(|h| h.to_str().ok());

    match (auth, pub_key) {
        (Some(a), Some(p)) if a.starts_with("Bearer ") => {
            // For now, accept a mock validation to keep proxy simple and fast
            // In a real system, we would check the Postgres DB or Redis cache here
            if p == "pk_default" && a == "Bearer sk_default" {
                Ok("proj_default".to_string())
            } else {
                Err(StatusCode::UNAUTHORIZED)
            }
        }
        _ => Err(StatusCode::UNAUTHORIZED),
    }
}

async fn ingest_traces(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(payload): Json<Value>,
) -> impl IntoResponse {
    let _tenant_id = match validate_key(&headers, &state).await {
        Ok(id) => id,
        Err(e) => return e.into_response(),
    };

    if let Some(traces) = payload.get("traces").and_then(|v| v.as_array()) {
        let mut records = Vec::with_capacity(traces.len());
        for trace in traces {
            let mut trace = trace.clone();
            trace["tenant_id"] = Value::String(_tenant_id.clone());
            let json_bytes = serde_json::to_vec(&trace).unwrap();
            
            records.push(Record {
                key: None,
                value: Some(json_bytes),
                headers: Default::default(),
                timestamp: chrono::Utc::now(),
            });
        }
        
        if let Err(e) = state.trace_producer.produce(records, Compression::NoCompression).await {
            error!("Failed to produce trace to Kafka: {}", e);
            return StatusCode::INTERNAL_SERVER_ERROR.into_response();
        }
    }

    StatusCode::ACCEPTED.into_response()
}

async fn ingest_spans(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(payload): Json<Value>,
) -> impl IntoResponse {
    let _tenant_id = match validate_key(&headers, &state).await {
        Ok(id) => id,
        Err(e) => return e.into_response(),
    };

    if let Some(spans) = payload.get("spans").and_then(|v| v.as_array()) {
        let mut records = Vec::with_capacity(spans.len());
        for span in spans {
            let mut span = span.clone();
            span["tenant_id"] = Value::String(_tenant_id.clone());
            let json_bytes = serde_json::to_vec(&span).unwrap();
            
            records.push(Record {
                key: None,
                value: Some(json_bytes),
                headers: Default::default(),
                timestamp: chrono::Utc::now(),
            });
        }
        
        if let Err(e) = state.span_producer.produce(records, Compression::NoCompression).await {
            error!("Failed to produce span to Kafka: {}", e);
            return StatusCode::INTERNAL_SERVER_ERROR.into_response();
        }
    }

    StatusCode::ACCEPTED.into_response()
}

pub mod telemetry {
    tonic::include_proto!("telemetry");
}

use telemetry::ingestion_service_server::{IngestionService, IngestionServiceServer};
use telemetry::{TracePayload, SpanPayload, IngestResponse};
use tonic::{Request, Response, Status};

pub struct GrpcIngestionService {
    trace_producer: Arc<PartitionClient>,
    span_producer: Arc<PartitionClient>,
}

#[tonic::async_trait]
impl IngestionService for GrpcIngestionService {
    async fn ingest_trace(
        &self,
        request: Request<TracePayload>,
    ) -> Result<Response<IngestResponse>, Status> {
        let payload = request.into_inner();
        let json_obj = serde_json::json!({
            "trace_id": payload.trace_id,
            "session_id": payload.session_id,
            "project_id": payload.project_id,
            "tenant_id": payload.tenant_id,
            "trace_name": payload.trace_name,
            "status": payload.status,
            "start_time": payload.start_time,
            "end_time": payload.end_time,
            "input": payload.input,
            "output": payload.output,
            "error_message": payload.error_message,
            "total_tokens": payload.total_tokens,
            "total_cost": payload.total_cost,
        });

        let json_bytes = serde_json::to_vec(&json_obj).unwrap();
        let record = Record {
            key: None,
            value: Some(json_bytes),
            headers: Default::default(),
            timestamp: chrono::Utc::now(),
        };

        if let Err(e) = self.trace_producer.produce(vec![record], Compression::NoCompression).await {
            error!("gRPC Failed to produce trace to Kafka: {}", e);
            return Err(Status::internal("Kafka Error"));
        }
        Ok(Response::new(IngestResponse { success: true, message: "OK".into() }))
    }

    async fn ingest_span(
        &self,
        request: Request<SpanPayload>,
    ) -> Result<Response<IngestResponse>, Status> {
        let payload = request.into_inner();
        let json_obj = serde_json::json!({
            "span_id": payload.span_id,
            "trace_id": payload.trace_id,
            "parent_id": payload.parent_id,
            "name": payload.name,
            "span_type": payload.span_type,
            "status": payload.status,
            "start_time": payload.start_time,
            "end_time": payload.end_time,
            "input": payload.input,
            "output": payload.output,
            "error_message": payload.error_message,
            "total_tokens": payload.total_tokens,
        });

        let json_bytes = serde_json::to_vec(&json_obj).unwrap();
        let record = Record {
            key: None,
            value: Some(json_bytes),
            headers: Default::default(),
            timestamp: chrono::Utc::now(),
        };

        if let Err(e) = self.span_producer.produce(vec![record], Compression::NoCompression).await {
            error!("gRPC Failed to produce span to Kafka: {}", e);
            return Err(Status::internal("Kafka Error"));
        }
        Ok(Response::new(IngestResponse { success: true, message: "OK".into() }))
    }
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();
    info!("Starting Rust Edge Ingestion Proxy...");

    let kafka_broker = std::env::var("KAFKA_BOOTSTRAP_SERVERS").unwrap_or_else(|_| "localhost:9092".to_string());
    
    // Setup Kafka client
    let client = ClientBuilder::new(vec![kafka_broker.clone()])
        .build()
        .await
        .expect("Failed to connect to Kafka");

    let trace_partition = Arc::new(client.partition_client("ingest_traces", 0, UnknownTopicHandling::Retry).await.expect("Failed to create trace partition client"));
    let span_partition = Arc::new(client.partition_client("ingest_spans", 0, UnknownTopicHandling::Retry).await.expect("Failed to create span partition client"));

    let app_state = AppState {
        trace_producer: trace_partition.clone(),
        span_producer: span_partition.clone(),
        key_cache: Arc::new(RwLock::new(std::collections::HashMap::new())),
    };

    let app = Router::new()
        .route("/api/ingest/traces", post(ingest_traces))
        .route("/api/ingest/spans", post(ingest_spans))
        .route("/api/v1/ingest/traces", post(ingest_traces))
        .route("/api/v1/ingest/spans", post(ingest_spans))
        .with_state(app_state);

    let axum_listener = tokio::net::TcpListener::bind("0.0.0.0:3001").await.unwrap();
    info!("Rust HTTP Proxy listening on 0.0.0.0:3001");
    
    let axum_server = axum::serve(axum_listener, app);

    // Setup gRPC Server
    let grpc_addr = "0.0.0.0:50051".parse().unwrap();
    let grpc_service = GrpcIngestionService {
        trace_producer: trace_partition.clone(),
        span_producer: span_partition.clone(),
    };
    
    info!("Rust gRPC Proxy listening on 0.0.0.0:50051");
    let grpc_server = tonic::transport::Server::builder()
        .add_service(IngestionServiceServer::new(grpc_service))
        .serve(grpc_addr);

    // Run both servers concurrently
    tokio::select! {
        _ = axum_server => { error!("Axum server crashed"); },
        _ = grpc_server => { error!("gRPC server crashed"); },
    }
}
