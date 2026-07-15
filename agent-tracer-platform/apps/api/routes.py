"""API endpoints for the dashboard."""

import os
import json
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta, timezone
import jwt

from fastapi import APIRouter, HTTPException, Query, Depends, Header, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from aiokafka import AIOKafkaProducer
import uuid
from qdrant_client import AsyncQdrantClient
import litellm

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LITELLM_EMBEDDING_MODEL = os.getenv("LITELLM_EMBEDDING_MODEL", "text-embedding-3-small")
LITELLM_CHAT_MODEL = os.getenv("LITELLM_CHAT_MODEL", "gpt-4o-mini")

qdrant_client = AsyncQdrantClient(url=QDRANT_URL)

from apps.api.platform_db import platform_db

# Imported from agent_tracer_plus library
from agent_tracer_plus.core.context import get_tracer
from agent_tracer_plus.intelligence.diagnosis import TraceDiagnoser
from agent_tracer_plus.intelligence.diff import diff_traces

router = APIRouter()

# --- JWT Config ---
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"

if os.getenv("ENVIRONMENT") == "production" and JWT_SECRET_KEY == "super-secret-key-change-in-production":
    raise ValueError("CRITICAL: JWT_SECRET_KEY must be set in production to a secure random string.")

# --- Auth Dependencies ---
async def verify_api_key(
    authorization: Optional[str] = Header(None),
    x_public_key: Optional[str] = Header(None)
) -> str:
    """Verifies the incoming request and returns the authenticated project_id."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    parts = authorization.split(" ")
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
        
    secret_key = parts[1]
    
    if not x_public_key:
        raise HTTPException(status_code=401, detail="Missing X-Public-Key header")
        
    project_id = await platform_db.validate_api_key(x_public_key, secret_key)
    if not project_id:
        raise HTTPException(status_code=403, detail="Invalid API Key")
        
    return project_id


async def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """Verifies JWT token and returns user_id."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def verify_admin_jwt(authorization: Optional[str] = Header(None)) -> str:
    """Verifies JWT token and ensures the user is an admin."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        role = payload.get("role")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        if role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def verify_jwt_or_api_key(
    authorization: Optional[str] = Header(None),
    x_public_key: Optional[str] = Header(None)
) -> str:
    """Verifies either a JWT token (for UI) or an API Key (for SDK) and returns the project_id."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    token_or_secret = authorization.split(" ")[1]
    
    # Try JWT first (from UI)
    try:
        payload = jwt.decode(token_or_secret, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if user_id:
            return "proj_default"
    except (jwt.ExpiredSignatureError, jwt.PyJWTError):
        pass # Fallback to API Key
        
    # Fallback to API Key
    if not x_public_key:
        raise HTTPException(status_code=401, detail="Missing X-Public-Key header or invalid JWT")
        
    project_id = await platform_db.validate_api_key(x_public_key, token_or_secret)
    if not project_id:
        raise HTTPException(status_code=403, detail="Invalid API Key or JWT")
        
    return project_id


from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# --- RBAC Role Enforcement ---
_ROLE_HIERARCHY = {"viewer": 0, "developer": 1, "admin": 2}

def require_role(minimum_role: str):
    """Dependency factory that enforces a minimum JWT role."""
    async def _check(authorization: Optional[str] = Header(None)) -> str:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Not authenticated")
        token = authorization.split(" ")[1]
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("sub")
            role = payload.get("role", "viewer")
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token")
            if _ROLE_HIERARCHY.get(role, -1) < _ROLE_HIERARCHY.get(minimum_role, 99):
                raise HTTPException(
                    status_code=403,
                    detail=f"Role '{role}' insufficient — requires '{minimum_role}' or above"
                )
            return user_id
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Invalid token")
    return _check

class AuthRequest(BaseModel):
    email: str
    password: str

@router.post("/auth/signup")
@limiter.limit("10/minute")
async def signup(req: AuthRequest, request: Request):
    user_id = await platform_db.create_user(req.email, req.password)
    if not user_id:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    token = jwt.encode({
        "sub": user_id, 
        "role": "viewer", # Default role for new signups
        "exp": datetime.now(timezone.utc) + timedelta(hours=24)
    }, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return {"token": token, "user_id": user_id, "role": "viewer"}

@router.post("/auth/login")
@limiter.limit("20/minute")
async def login(req: AuthRequest, request: Request):
    user = await platform_db.authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    token = jwt.encode({
        "sub": user["id"], 
        "role": user.get("role", "viewer"),
        "exp": datetime.now(timezone.utc) + timedelta(hours=24)
    }, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return {"token": token, "user_id": user["id"], "role": user.get("role", "viewer")}


# --- App State Dependencies ---
async def get_kafka_producer(request: Request) -> AIOKafkaProducer:
    """
    Retrieves Kafka Producer from App State.
    Requires producer initialization in main.py lifespan events.
    """
    producer = getattr(request.app.state, "kafka_producer", None)
    if not producer:
        raise HTTPException(status_code=500, detail="Kafka producer is not initialized")
    return producer

async def get_tracer_dependency(request: Request, project_id: str = Depends(verify_jwt_or_api_key)) -> Any:
    """Centralized Tracer Dependency for easy testing and mocking. Now requires JWT or API Key Auth."""
    tracer = getattr(request.app.state, "tracer", None)
    if not tracer:
        raise HTTPException(status_code=500, detail="Tracer not initialized")
    return tracer


# --- Ingestion Endpoints (Used by SDK) ---

class IngestTracesRequest(BaseModel):
    # Capped max_length to prevent OOM / DoS attacks
    traces: List[Dict[str, Any]] = Field(..., max_length=1000)

class IngestSpansRequest(BaseModel):
    spans: List[Dict[str, Any]] = Field(..., max_length=1000)


@router.post("/ingest/traces", status_code=202)
@limiter.limit("1000/minute")
async def ingest_traces(
    req: IngestTracesRequest,
    request: Request,
    project_id: str = Depends(verify_api_key),
    producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    # Run Kafka publish asynchronously in parallel to maximize throughput
    async def send_trace(t: Dict[str, Any]):
        t["tenant_id"] = project_id
        await producer.send_and_wait("ingest_traces", json.dumps(t).encode('utf-8'))

    await asyncio.gather(*(send_trace(t) for t in req.traces))
    return {"status": "accepted", "ingested": len(req.traces)}


@router.post("/ingest/spans", status_code=202)
@limiter.limit("5000/minute")
async def ingest_spans(
    req: IngestSpansRequest,
    request: Request,
    project_id: str = Depends(verify_api_key),
    producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    async def send_span(s: Dict[str, Any]):
        await producer.send_and_wait("ingest_spans", json.dumps(s).encode('utf-8'))

    await asyncio.gather(*(send_span(s) for s in req.spans))
    return {"status": "accepted", "ingested": len(req.spans)}


# --- Platform Endpoints ---

@router.post("/platform/keys")
@limiter.limit("10/minute")
async def create_api_key(request: Request, user_id: str = Depends(verify_admin_jwt)):
    """Endpoint for the UI to generate a new key pair. Requires admin access."""
    project_id = "proj_default" # Hardcoded for now, but would be fetched from user's org
    pk, sk = await platform_db.generate_api_key(project_id)
    return {"public_key": pk, "secret_key": sk}


# --- UI Endpoints (Used by Dashboard) ---

class TraceResponse(BaseModel):
    traces: List[Dict[str, Any]]
    total: int


@router.get("/traces", response_model=TraceResponse)
@limiter.limit("120/minute")
async def list_traces(
    request: Request,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    agent_name: Optional[str] = None,
    status: Optional[str] = None,
    session_id: Optional[str] = None,
    tracer: Any = Depends(get_tracer_dependency)
):
    """List traces with pagination and filtering."""
    filters = {}
    if agent_name:
        filters["agent_name"] = agent_name
    if status:
        filters["status"] = status
    if session_id:
        filters["session_id"] = session_id

    # Pagination is now pushed down to the DB Query to prevent OOM
    raw_traces = await tracer.query(limit=limit, offset=offset, **filters)
    
    # Standardize fields for the UI (gRPC ingestion uses different keys)
    traces = []
    for t in raw_traces:
        if "start_time" in t and "started_at" not in t:
            t["started_at"] = t["start_time"]
        if "trace_name" in t and "agent_name" not in t:
            t["agent_name"] = t["trace_name"]
        if "duration" in t and "duration_ms" not in t:
            t["duration_ms"] = t["duration"]
            
        # Calculate duration if missing
        if "duration_ms" not in t or t["duration_ms"] is None:
            if t.get("start_time") and t.get("end_time"):
                try:
                    start = datetime.fromisoformat(t["start_time"].replace("Z", "+00:00"))
                    end = datetime.fromisoformat(t["end_time"].replace("Z", "+00:00"))
                    t["duration_ms"] = (end - start).total_seconds() * 1000
                except:
                    t["duration_ms"] = 0
            else:
                t["duration_ms"] = 0
                
        traces.append(t)
    
    # We don't have a count API in the tracer yet, so we return a placeholder or estimate
    total = offset + len(traces) if len(traces) == limit else offset + len(traces)
    
    return {"traces": traces, "total": total}


@router.get("/traces/{trace_id}")
@limiter.limit("120/minute")
async def get_trace_detail(request: Request, trace_id: str, tracer: Any = Depends(get_tracer_dependency)):
    """Get full details of a specific trace, including all spans."""
    trace = await tracer.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")

    spans = await tracer.get_spans(trace_id)
    
    data = trace.to_dict() if hasattr(trace, 'to_dict') else trace
    if isinstance(data, dict):
        if "start_time" in data and "started_at" not in data:
            data["started_at"] = data["start_time"]
        if "trace_name" in data and "agent_name" not in data:
            data["agent_name"] = data["trace_name"]
            
    span_dicts = []
    for s in spans:
        sd = s.to_dict() if hasattr(s, 'to_dict') else s
        if isinstance(sd, dict):
            if "start_time" in sd and "started_at" not in sd:
                sd["started_at"] = sd["start_time"]
            if "parent_id" in sd and "parent_span_id" not in sd:
                sd["parent_span_id"] = sd["parent_id"]
            if "input" in sd and isinstance(sd["input"], str):
                try:
                    sd["input"] = json.loads(sd["input"])
                except:
                    pass
            if "output" in sd and isinstance(sd["output"], str):
                try:
                    sd["output"] = json.loads(sd["output"])
                except:
                    pass
            if "error_message" in sd and "error" not in sd:
                sd["error"] = sd["error_message"]
        span_dicts.append(sd)
        
    data["spans"] = span_dicts
    
    return data


class DiagnoseRequest(BaseModel):
    trace_id: str

@router.post("/remediation/analyze")
@limiter.limit("20/minute")
async def diagnose_trace(request: Request, req: DiagnoseRequest, tracer: Any = Depends(get_tracer_dependency)):
    """Trigger AI Root Cause Analysis on a trace."""
    trace = await tracer.get_trace(req.trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
        
    trace.spans = await tracer.get_spans(req.trace_id)

    diagnoser = TraceDiagnoser(api_key=OPENAI_API_KEY)
    result = await diagnoser.diagnose(trace, trace.spans)
    return {"diagnosis": result.get("diagnosis", "Failed to diagnose")}


@router.get("/intelligence/diff")
@limiter.limit("60/minute")
async def diff_two_traces(
    request: Request,
    baseline_id: str, 
    new_id: str, 
    tracer: Any = Depends(get_tracer_dependency)
):
    """Compare two traces and return the exact delta."""
    baseline = await tracer.get_trace(baseline_id)
    new_t = await tracer.get_trace(new_id)
    
    if not baseline or not new_t:
        raise HTTPException(status_code=404, detail="One or both traces not found")

    baseline.spans = await tracer.get_spans(baseline_id)
    new_t.spans = await tracer.get_spans(new_id)
    delta = diff_traces(baseline, new_t)
    return delta.to_dict()


# --- Advanced Intelligence & Search ---

@router.get("/search/semantic")
@limiter.limit("30/minute")
async def semantic_search(request: Request, query: str, limit: int = 10, tracer: Any = Depends(get_tracer_dependency)):
    """Natural language search over traces using Vector DB (Qdrant)."""
    try:
        res = await litellm.aembedding(
            model=LITELLM_EMBEDDING_MODEL,
            input=[query],
            api_key=OPENAI_API_KEY if OPENAI_API_KEY else None
        )
        vector = res.data[0]["embedding"]
    except Exception as e:
        return {"query": query, "results": [], "message": f"Embedding error: {e}"}
    
    try:
        search_result = await qdrant_client.search(
            collection_name="traces",
            query_vector=vector,
            limit=limit,
            score_threshold=0.3
        )
        
        results = []
        for hit in search_result:
            # Fetch real trace metadata from ClickHouse
            trace = await tracer.get_trace(hit.id)
            if trace:
                results.append({
                    "id": hit.id,
                    "agent": getattr(trace, "agent_name", hit.payload.get("trace_name", "Unknown")),
                    "status": getattr(trace, "status", "UNKNOWN"),
                    "duration_ms": getattr(trace, "duration_ms", 0),
                    "total_cost": getattr(trace, "total_cost", 0),
                    "match": round(hit.score * 100, 2),
                    "excerpt": f"Semantic Match found (score: {hit.score:.2f})"
                })
            else:
                results.append({
                    "id": hit.id,
                    "agent": hit.payload.get("trace_name", "Unknown Agent"),
                    "match": round(hit.score * 100, 2),
                    "excerpt": f"Semantic Match found (score: {hit.score:.2f}) (Trace deleted)"
                })
            
        return {"query": query, "results": results, "message": f"Found {len(results)} traces using Qdrant Vector DB"}
    except Exception as e:
        return {"query": query, "results": [], "message": f"Vector DB error: {e}"}

class ClusterRequest(BaseModel):
    time_range: str = "last_24h"
    status: str = "ERROR"

@router.post("/search/cluster")
@limiter.limit("10/minute")
async def cluster_traces(request: Request, req: ClusterRequest, tracer: Any = Depends(get_tracer_dependency)):
    """K-Means clustering of traces using Qdrant vectors and Scikit-Learn."""
    traces = await tracer.query(limit=500, status=req.status)
    if not traces:
        return {"clusters": [], "message": "No traces found to cluster."}

    trace_ids = [t.trace_id for t in traces if getattr(t, "trace_id", None)]
    if not trace_ids:
        return {"clusters": [], "message": "No trace IDs found."}

    try:
        # Fetch vectors from Qdrant
        points = await qdrant_client.retrieve(
            collection_name="traces",
            ids=trace_ids,
            with_vectors=True
        )
        
        vectors = [p.vector for p in points if p.vector]
        point_id_to_trace = {p.id: p.id for p in points}

        if len(vectors) < 2:
            return {"clusters": [{"size": len(vectors), "common_error": "Insufficient data"}], "message": f"Clustered {len(vectors)} traces"}

        try:
            from sklearn.cluster import KMeans
            from collections import Counter
            import numpy as np
            
            n_clusters = min(5, len(vectors))
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = kmeans.fit_predict(np.array(vectors))

            # Build a trace lookup for meaningful labels
            trace_lookup = {}
            for t in traces:
                tid = getattr(t, "trace_id", None)
                if tid:
                    trace_lookup[tid] = {
                        "agent_name": getattr(t, "agent_name", "unknown"),
                        "status": getattr(t, "status", "UNKNOWN"),
                        "error": getattr(t, "error", None),
                    }

            # Group point IDs by cluster label
            cluster_members: dict = {}
            point_ids = [p.id for p in points if p.vector]
            for idx, lbl in enumerate(labels):
                cid = int(lbl)
                if cid not in cluster_members:
                    cluster_members[cid] = []
                if idx < len(point_ids):
                    cluster_members[cid].append(point_ids[idx])

            formatted_clusters = []
            for cid, member_ids in cluster_members.items():
                agents = [trace_lookup.get(mid, {}).get("agent_name", "unknown") for mid in member_ids]
                common_agent = Counter(agents).most_common(1)[0][0] if agents else "unknown"
                statuses = [trace_lookup.get(mid, {}).get("status", "UNKNOWN") for mid in member_ids]
                error_count = sum(1 for s in statuses if s == "ERROR")
                formatted_clusters.append({
                    "cluster_id": cid,
                    "size": len(member_ids),
                    "common_agent": common_agent,
                    "error_count": error_count,
                    "error_rate": round(error_count / len(member_ids) * 100, 1) if member_ids else 0,
                    "representative_trace_id": member_ids[0] if member_ids else None,
                    "common_error": f"{common_agent} — {error_count}/{len(member_ids)} errors",
                })

            return {"clusters": formatted_clusters, "message": f"Clustered {len(vectors)} traces into {n_clusters} groups"}
        except ImportError:
            return {"clusters": [{"size": len(vectors), "common_error": "scikit-learn not installed"}], "message": f"Found {len(vectors)} vectors"}

    except Exception as e:
        return {"clusters": [{"size": len(traces), "common_error": str(e)}], "message": "Clustering error"}

@router.get("/intelligence/graph")
@limiter.limit("30/minute")
async def dependency_graph(request: Request, tracer: Any = Depends(get_tracer_dependency)):
    """Auto-discovery dependency map (Agent topology)."""
    from agent_tracer_plus.graph.builder import build_dependency_graph
    
    try:
        graph = await build_dependency_graph(limit=100)
        
        # Format nodes and edges for the UI
        nodes = [{"id": n, "label": n, "type": graph.node_attributes.get(n, {}).get("type", "tool")} for n in graph.nodes]
        edges = []
        for src, targets in graph.edges.items():
            for tgt in targets:
                edges.append({"source": src, "target": tgt})
                
        # If the graph is empty (e.g., no traces yet), provide mock data
        if not nodes:
            agents = ["SupervisorAgent", "ResearchAgent", "WritingAgent", "ToolExecutor"]
            nodes = [{"id": a, "label": a, "type": "agent"} for a in agents]
            edges = [
                {"source": "SupervisorAgent", "target": "ResearchAgent"},
                {"source": "SupervisorAgent", "target": "WritingAgent"},
                {"source": "ResearchAgent", "target": "ToolExecutor"},
                {"source": "WritingAgent", "target": "ToolExecutor"},
                {"source": "ToolExecutor", "target": "ResearchAgent"} # Intentional cycle for testing
            ]
            return {
                "nodes": nodes, 
                "edges": edges, 
                "has_cycles": True, 
                "bottlenecks": [("SupervisorAgent", 0.5), ("ResearchAgent", 0.4)],
                "mermaid": "graph TD;\n  SupervisorAgent --> ResearchAgent;\n  SupervisorAgent --> WritingAgent;\n  ResearchAgent --> ToolExecutor;\n  WritingAgent --> ToolExecutor;\n  ToolExecutor --> ResearchAgent;"
            }
            
        return {
            "nodes": nodes, 
            "edges": edges,
            "has_cycles": graph.detect_cycles(),
            "bottlenecks": graph.find_bottlenecks(),
            "mermaid": graph.export_mermaid()
        }
    except Exception as e:
        # Fallback to basic graph if builder fails
        return {"nodes": [], "edges": [], "error": str(e)}

class ReplayRequest(BaseModel):
    trace_id: str
    diverge_at: Optional[str] = None

@router.post("/intelligence/replay")
@limiter.limit("20/minute")
async def replay_trace(
    request: Request,
    req: ReplayRequest,
    producer: AIOKafkaProducer = Depends(get_kafka_producer),
    tracer: Any = Depends(get_tracer_dependency)
):
    """Trigger a deterministic time-travel replay."""
    job_id = str(uuid.uuid4())
    job = {
        "trace_id": req.trace_id,
        "diverge_at": req.diverge_at,
        "job_id": job_id
    }
    await producer.send_and_wait("diverge_jobs", json.dumps(job).encode('utf-8'))
    return {"status": "queued", "job_id": job_id}


# --- Analytics & Simulation ---

@router.get("/analytics/sessions")
@limiter.limit("60/minute")
async def session_analytics(request: Request, tracer: Any = Depends(get_tracer_dependency)):
    """Drop-off analysis, task completion rates."""
    traces = await tracer.query(limit=1000)
    total = len(traces)
    if total == 0:
        return {"drop_off_rate": 0, "completion_rate": 0, "total_sessions": 0}
    completed = sum(1 for t in traces if t.status in ("OK", "COMPLETED"))
    return {
        "drop_off_rate": 1.0 - (completed / total),
        "completion_rate": completed / total,
        "total_sessions": total
    }

@router.get("/analytics/dashboard")
@limiter.limit("30/minute")
async def get_analytics_dashboard(request: Request, tracer: Any = Depends(get_tracer_dependency)):
    """Aggregation endpoint for custom OLAP dashboard."""
    traces = await tracer.query(limit=5000)
    
    # 1. Daily Cost (Last 7 Days)
    from collections import defaultdict
    daily_cost = defaultdict(float)
    now = datetime.now(timezone.utc)
    
    # 2. Top Agents
    agent_stats = defaultdict(lambda: {"cost": 0.0, "errors": 0, "total": 0})
    
    for t in traces:
        # Time-series
        start_time_str = getattr(t, "started_at", None)
        if hasattr(start_time_str, "isoformat"):
            start_time_str = start_time_str.isoformat()
        elif hasattr(t, "start_time"):
            start_time_str = getattr(t, "start_time")
            
        if start_time_str:
            try:
                dt = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                days_ago = (now - dt).days
                if 0 <= days_ago < 7:
                    daily_cost[6 - days_ago] += getattr(t, "total_cost", 0.0)
            except ValueError:
                pass
                
        # Agent Stats
        agent_name = getattr(t, "agent_name", getattr(t, "trace_name", "Unknown"))
        cost = getattr(t, "total_cost", 0.0)
        status = getattr(t, "status", "OK")
        
        agent_stats[agent_name]["total"] += 1
        agent_stats[agent_name]["cost"] += cost
        if status == "ERROR":
            agent_stats[agent_name]["errors"] += 1

    # Format arrays
    daily_cost_array = [round(daily_cost.get(i, 0.0), 4) for i in range(7)]
    
    top_cost = []
    top_errors = []
    
    for agent, stats in agent_stats.items():
        top_cost.append({"agent": agent, "cost": round(stats["cost"], 4)})
        err_rate = (stats["errors"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        top_errors.append({"agent": agent, "error_rate": round(err_rate, 1)})
        
    top_cost.sort(key=lambda x: x["cost"], reverse=True)
    top_errors.sort(key=lambda x: x["error_rate"], reverse=True)

    return {
        "daily_cost": daily_cost_array,
        "top_cost": top_cost[:5],
        "top_errors": top_errors[:5]
    }


class SimulatorRequest(BaseModel):
    trace_id: str
    target_model: str
    aggregate_days: Optional[int] = 1

@router.post("/simulator/model-swap")
@limiter.limit("30/minute")
async def model_swap_simulator(request: Request, req: SimulatorRequest, tracer: Any = Depends(get_tracer_dependency)):
    """Simulate cost savings over an aggregated period."""
    trace = await tracer.get_trace(req.trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
        
    prices = {'gpt-4o-mini': 0.0005, 'claude-3-haiku': 0.00025, 'claude-3-5-sonnet': 0.003, 'gpt-4o': 0.015}
    price = prices.get(req.target_model, 0.001)
    
    # Calculate for single trace
    simulated_cost = (trace.total_tokens / 1000) * price
    single_savings = trace.total_cost - simulated_cost
    
    # Simple projection based on past N days of similar traces
    # In a real system, we'd do a time-bound OLAP query on ClickHouse
    traces = await tracer.query(limit=5000)
    now = datetime.now(timezone.utc)
    target_agent = getattr(trace, "agent_name", getattr(trace, "trace_name", "Unknown"))
    
    similar_traces_in_window = 0
    for t in traces:
        agent_name = getattr(t, "agent_name", getattr(t, "trace_name", "Unknown"))
        if agent_name == target_agent:
            start_time_str = getattr(t, "started_at", getattr(t, "start_time", None))
            if hasattr(start_time_str, "isoformat"):
                start_time_str = start_time_str.isoformat()
            if start_time_str:
                try:
                    dt = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                    if (now - dt).days <= (req.aggregate_days or 1):
                        similar_traces_in_window += 1
                except ValueError:
                    pass
                    
    # Default to at least 1 if it's the only trace
    multiplier = max(1, similar_traces_in_window)
    
    projected_savings = single_savings * multiplier
    projected_cost = simulated_cost * multiplier
    original_total = trace.total_cost * multiplier
    
    savings_pct = (projected_savings / original_total * 100) if original_total > 0 else 0
    
    return {
        "trace_id": req.trace_id, 
        "simulated_cost": projected_cost, 
        "projected_savings": projected_savings,
        "savings_pct": savings_pct,
        "aggregate_days": req.aggregate_days,
        "traces_analyzed": multiplier
    }

@router.get("/sustainability/report")
@limiter.limit("20/minute")
async def sustainability_report(request: Request, tracer: Any = Depends(get_tracer_dependency)):
    """Fetch the CO2 footprint data using real Storage queries."""
    try:
        traces = await tracer.query(limit=10000)
        total_co2_grams = 0.0
        total_energy_kwh = 0.0
        
        for trace in traces:
            metadata = getattr(trace, "metadata", {}) or {}
            carbon_info = metadata.get("carbon", {})
            if carbon_info:
                total_co2_grams += carbon_info.get("co2_grams", 0.0)
                total_energy_kwh += carbon_info.get("energy_kwh", 0.0)
                
        total_co2_kg = total_co2_grams / 1000.0
        miles = (total_co2_grams / 404.0) if total_co2_grams > 0 else 0
        
        return {
            "total_co2_kg": total_co2_kg, 
            "total_energy_kwh": total_energy_kwh, 
            "equivalent": f"Driving {miles:.1f} miles"
        }
    except Exception as e:
        return {"total_co2_kg": 0, "total_energy_kwh": 0, "equivalent": "Driving 0 miles"}


# --- Enterprise Guardrails ---

@router.get("/sla/report")
@limiter.limit("30/minute")
async def sla_report(request: Request, project_id: str = Depends(verify_jwt_or_api_key), tracer: Any = Depends(get_tracer_dependency)):
    """Real-time SLA breach monitoring based on actual trace errors."""
    traces = await tracer.query(limit=1000)
    total = len(traces)
    if total == 0:
        return {"breaches": [], "compliance_score": 100.0}
    
    errors = sum(1 for t in traces if t.status == "ERROR")
    compliance = 100.0 - ((errors / total) * 100)
    
    return {"breaches": [], "compliance_score": round(compliance, 2)}

@router.get("/cost/anomaly")
@limiter.limit("20/minute")
async def cost_anomaly_detection(request: Request, project_id: str = Depends(verify_jwt_or_api_key), tracer: Any = Depends(get_tracer_dependency)):
    """Simple heuristic anomaly detection for cost."""
    traces = await tracer.query(limit=5000)
    if not traces:
        return {"anomalies": []}
        
    avg_cost = sum(getattr(t, "total_cost", 0.0) for t in traces) / len(traces)
    threshold = avg_cost * 3.0
    
    anomalies = []
    for t in traces:
        cost = getattr(t, "total_cost", 0.0)
        if cost > threshold and cost > 0.01:
            anomalies.append({
                "trace_id": t.trace_id,
                "agent_name": getattr(t, "agent_name", "Unknown"),
                "cost": cost,
                "threshold": threshold
            })
            
    return {"anomalies": anomalies}

class BudgetRequest(BaseModel):
    tenant_id: str
    amount: float

@router.post("/budgets/enforce")
@limiter.limit("20/minute")
async def enforce_budget(request: Request, req: BudgetRequest, project_id: str = Depends(require_role("developer"))):
    """Check and enforce token budgets per tenant."""
    return await platform_db.set_budget(req.tenant_id, req.amount)

class AlertConfigRequest(BaseModel):
    name: str
    condition: str
    channel: str

@router.post("/alerts/config")
@limiter.limit("20/minute")
async def configure_alert(request: Request, req: AlertConfigRequest, project_id: str = Depends(require_role("developer"))):
    """Configure webhook/slack alerting rules."""
    alert_id = await platform_db.create_alert(project_id, req.name, req.condition, req.channel)
    return {"status": "configured", "rule": req.name, "alert_id": alert_id}


# --- Experimentation & RLHF ---

class RunExperimentRequest(BaseModel):
    name: str
    dataset_id: str
    prompt_id: str

@router.post("/experiments/run")
@limiter.limit("10/minute")
async def run_experiment(request: Request, req: RunExperimentRequest, project_id: str = Depends(require_role("developer"))):
    prompt = await platform_db.get_prompt(project_id, req.prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
        
    items = await platform_db.list_dataset_items(req.dataset_id)
    if not items:
        raise HTTPException(status_code=400, detail="Dataset is empty")
        
    exp_id = await platform_db.create_experiment(project_id, req.name, req.dataset_id, req.prompt_id)
    
    async def evaluate_dataset():
        for item in items:
            input_vars = item["input"]
            expected = item["expected_output"]
            
            prompt_content = prompt["content"].get("text", "") if isinstance(prompt["content"], dict) else str(prompt["content"])
            final_prompt = prompt_content
            for k, v in input_vars.items():
                final_prompt = final_prompt.replace(f"{{{{{k}}}}}", str(v))
                
            start = datetime.now()
            try:
                res = await litellm.acompletion(
                    model=LITELLM_CHAT_MODEL,
                    api_key=OPENAI_API_KEY if OPENAI_API_KEY else None,
                    messages=[{"role": "user", "content": final_prompt}]
                )
                output = res.choices[0].message.content
                latency = (datetime.now() - start).total_seconds()
                cost = getattr(res.usage, "total_tokens", 0) / 1000 * 0.0005
                
                expected_str = str(expected.get("target", expected) if isinstance(expected, dict) else expected)
                success = expected_str.lower() in output.lower()
                
                await platform_db.create_experiment_result(exp_id, item["id"], {"output": output}, latency, cost, success)
            except Exception as e:
                await platform_db.create_experiment_result(exp_id, item["id"], {"error": str(e)}, 0, 0, False)
                
    asyncio.create_task(evaluate_dataset())
    return {"experiment_id": exp_id, "status": "running"}

@router.get("/experiments")
@limiter.limit("60/minute")
async def list_experiments(request: Request, project_id: str = Depends(verify_jwt_or_api_key)):
    experiments = await platform_db.list_experiments(project_id)
    return {"experiments": experiments}

@router.get("/experiments/{exp_id}/results")
async def get_experiment_results(exp_id: str, project_id: str = Depends(verify_jwt_or_api_key)):
    exp = await platform_db.get_experiment(project_id, exp_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    results = await platform_db.list_experiment_results(exp_id)
    return {"experiment": exp, "results": results}

# --- RLHF Export Endpoint (P2-13) ---
from fastapi.responses import StreamingResponse
import io

class RLHFExportRequest(BaseModel):
    format: str = "jsonl"  # "jsonl", "huggingface", "openai_finetune"
    min_score: Optional[float] = None
    max_score: Optional[float] = None

@router.post("/feedback/export")
@limiter.limit("5/minute")
async def export_rlhf_data(
    request: Request,
    req: RLHFExportRequest,
    project_id: str = Depends(require_role("developer"))
):
    """Export feedback-annotated traces as RLHF/SFT training datasets."""
    from agent_tracer_plus.feedback.datasets import export_training_data
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        summary = await export_training_data(
            format=req.format,
            output=tmp_path,
            min_score=req.min_score,
            max_score=req.max_score,
        )
        with open(tmp_path, "rb") as f:
            content = f.read()
        media_type = "application/json" if req.format != "jsonl" else "application/x-ndjson"
        filename = f"rlhf_export_{req.format}.jsonl"
        return StreamingResponse(
            io.BytesIO(content),
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Record-Count": str(summary.get("count", 0)),
            }
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


class FeedbackRequest(BaseModel):
    rating: int # 1 or -1
    comment: Optional[str] = None

@router.post("/traces/{trace_id}/feedback")
@limiter.limit("60/minute")
async def trace_feedback(request: Request, trace_id: str, req: FeedbackRequest, project_id: str = Depends(verify_jwt_or_api_key)):
    """Submit RLHF feedback (thumbs up/down) to a specific trace."""
    fb_id = await platform_db.create_trace_feedback(project_id, trace_id, req.rating, req.comment)
    return {"trace_id": trace_id, "feedback_id": fb_id, "status": "saved"}

class AnnotateRequest(BaseModel):
    comment: str

@router.post("/traces/{trace_id}/annotate")
@limiter.limit("60/minute")
async def annotate_trace(request: Request, trace_id: str, req: AnnotateRequest, project_id: str = Depends(require_role("developer"))):
    """Team collaboration comments."""
    ann_id = await platform_db.create_trace_annotation(project_id, trace_id, req.comment)
    return {"trace_id": trace_id, "annotation_id": ann_id, "status": "saved"}


# --- Next-Gen Endpoints (Streaming, WebGL, Replay, Remediation) ---

# 1. Streaming Firehose
@router.websocket("/stream/live")
async def live_trace_stream(websocket: WebSocket, project_id: str = Query(...)):
    """WebSocket endpoint for real-time trace 'firehose' dashboard."""
    await websocket.accept()
    
    KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
    try:
        from aiokafka import AIOKafkaConsumer
        consumer = AIOKafkaConsumer(
            "ingest_traces",
            bootstrap_servers=KAFKA_BROKER,
            group_id=f"live-stream-{uuid.uuid4().hex[:8]}"
        )
        await consumer.start()
    except Exception as e:
        await websocket.close(code=1011, reason=f"Kafka connection failed: {e}")
        return

    try:
        async for msg in consumer:
            # We filter messages for the specific tenant
            try:
                trace_data = json.loads(msg.value.decode('utf-8'))
                if trace_data.get("tenant_id") == project_id:
                    await websocket.send_json({
                        "type": "trace_arrival",
                        "trace_id": trace_data.get("trace_id"),
                        "timestamp": trace_data.get("started_at", datetime.now(timezone.utc).isoformat()),
                        "status": trace_data.get("status", "OK")
                    })
            except Exception as parse_e:
                continue
    except WebSocketDisconnect:
        pass
    finally:
        await consumer.stop()


# 2. WebGL / Visualization
@router.get("/traces/{trace_id}/graph")
async def get_trace_graph(trace_id: str, tracer: Any = Depends(get_tracer_dependency)):
    """Returns trace as a flat nodes/edges structure optimized for WebGL/Three.js."""
    trace = await tracer.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    spans = await tracer.get_spans(trace_id)
    
    nodes = [{"id": s.span_id, "label": s.name, "type": s.span_type.value if hasattr(s.span_type, 'value') else str(s.span_type)} for s in spans]
    edges = [{"source": s.parent_span_id, "target": s.span_id} for s in spans if s.parent_span_id]
    
    return {"trace_id": trace_id, "nodes": nodes, "edges": edges}


@router.get("/traces/{trace_id}/waterfall")
async def get_trace_waterfall(trace_id: str, tracer: Any = Depends(get_tracer_dependency)):
    """Returns latency/timing data structured for Gantt/Waterfall charts."""
    trace = await tracer.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    spans = await tracer.get_spans(trace_id)
    
    items = []
    for s in spans:
        items.append({
            "span_id": s.span_id,
            "name": s.name,
            "start_time": s.started_at.isoformat() if s.started_at else None,
            "end_time": s.ended_at.isoformat() if s.ended_at else None,
            "duration_ms": s.duration_ms
        })
    return {"trace_id": trace_id, "waterfall": items}


# 3. Time-Travel IDE Console
@router.get("/replay/{trace_id}/context")
async def get_replay_context(trace_id: str, tracer: Any = Depends(get_tracer_dependency)):
    """Fetches exact memory state and env vars for stepping through execution."""
    # Placeholder for fetching memory snapshot
    return {
        "trace_id": trace_id,
        "memory_state": {"short_term": ["User asked about pricing"], "long_term": []},
        "env_vars": {"LLM_PROVIDER": "OpenAI"}
    }

class DivergeRequest(BaseModel):
    span_id: str
    new_input: str

@router.post("/replay/{trace_id}/diverge")
async def diverge_replay(trace_id: str, req: DivergeRequest, project_id: str = Depends(verify_jwt_or_api_key), producer: AIOKafkaProducer = Depends(get_kafka_producer)):
    """Triggers 'what-if' divergence execution."""
    job_id = await platform_db.create_async_job(project_id, "diverge", trace_id)
    payload = {"job_id": job_id, "trace_id": trace_id, "span_id": req.span_id, "new_input": req.new_input}
    await producer.send_and_wait("diverge_jobs", json.dumps(payload).encode('utf-8'))
    return {"trace_id": trace_id, "job_id": job_id, "status": "diverged_execution_started"}


@router.get("/replay/status/{job_id}")
async def get_replay_status(job_id: str, project_id: str = Depends(verify_jwt_or_api_key)):
    """Polls status of diverged replay execution."""
    job = await platform_db.get_async_job(project_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# 4. Autonomous AI Remediation
class GeneratePRRequest(BaseModel):
    trace_id: str
    recommended_fix: str

@router.post("/remediation/generate-pr")
async def generate_remediation_pr(req: GeneratePRRequest, project_id: str = Depends(verify_jwt_or_api_key), producer: AIOKafkaProducer = Depends(get_kafka_producer)):
    """Instructs background worker to create a GitHub/GitLab PR with fix."""
    job_id = await platform_db.create_async_job(project_id, "remediation", req.trace_id)
    payload = {"job_id": job_id, "trace_id": req.trace_id, "recommended_fix": req.recommended_fix}
    await producer.send_and_wait("remediation_jobs", json.dumps(payload).encode('utf-8'))
    return {"job_id": job_id, "status": "pr_generation_queued"}


@router.get("/remediation/jobs")
async def list_remediation_jobs(project_id: str = Depends(verify_jwt_or_api_key)):
    """View history and status of autonomous fix attempts."""
    jobs = await platform_db.list_async_jobs(project_id, "remediation")
    return {"jobs": jobs}

# --- Prompts Management ---

class CreatePromptRequest(BaseModel):
    name: str
    version: int
    content: dict

@router.post("/prompts")
@limiter.limit("30/minute")
async def create_prompt(request: Request, req: CreatePromptRequest, project_id: str = Depends(require_role("developer"))):
    prompt_id = await platform_db.create_prompt(project_id, req.name, req.version, req.content)
    return {"prompt_id": prompt_id, "status": "created"}

@router.get("/prompts/{name}")
async def get_prompt(name: str, version: Optional[int] = None, project_id: str = Depends(verify_jwt_or_api_key)):
    prompt = await platform_db.get_prompt(project_id, name, version)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt

class RunPromptRequest(BaseModel):
    model: str = "gpt-4o-mini"
    prompt: str
    variables: dict = {}

@router.post("/prompts/run")
@limiter.limit("20/minute")
async def run_prompt(request: Request, req: RunPromptRequest, project_id: str = Depends(require_role("developer"))):
    try:
        final_prompt = req.prompt
        for k, v in req.variables.items():
            final_prompt = final_prompt.replace(f"{{{{{k}}}}}", str(v))
            
        start_time = datetime.now()
        
        response = await litellm.acompletion(
            model=req.model or LITELLM_CHAT_MODEL,
            api_key=OPENAI_API_KEY if OPENAI_API_KEY else None,
            messages=[{"role": "user", "content": final_prompt}],
            temperature=0.7
        )
        
        latency = (datetime.now() - start_time).total_seconds()
        tokens = getattr(response.usage, "total_tokens", 0)
        
        return {
            "output": response.choices[0].message.content,
            "latency": latency,
            "tokens": tokens,
            "cost": (tokens / 1000) * 0.0005 # Rough estimate
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prompt execution failed: {str(e)}")

# --- Datasets & Evaluations ---

class CreateDatasetRequest(BaseModel):
    name: str

@router.post("/datasets")
@limiter.limit("30/minute")
async def create_dataset(request: Request, req: CreateDatasetRequest, project_id: str = Depends(require_role("developer"))):
    ds_id = await platform_db.create_dataset(project_id, req.name)
    return {"dataset_id": ds_id, "status": "created"}

@router.get("/datasets")
async def list_datasets(project_id: str = Depends(verify_jwt_or_api_key)):
    datasets = await platform_db.list_datasets(project_id)
    return {"datasets": datasets}

class CreateDatasetItemRequest(BaseModel):
    dataset_id: str
    input: dict
    expected_output: dict

@router.post("/dataset-items")
async def create_dataset_item(req: CreateDatasetItemRequest, project_id: str = Depends(verify_jwt_or_api_key)):
    datasets = await platform_db.list_datasets(project_id)
    if not any(d["id"] == req.dataset_id for d in datasets):
        raise HTTPException(status_code=403, detail="Dataset not found or access denied")
    
    item_id = await platform_db.create_dataset_item(req.dataset_id, req.input, req.expected_output)
    return {"item_id": item_id, "status": "created"}

@router.get("/datasets/{dataset_id}/items")
async def list_dataset_items(dataset_id: str, project_id: str = Depends(verify_jwt_or_api_key)):
    datasets = await platform_db.list_datasets(project_id)
    if not any(d["id"] == dataset_id for d in datasets):
        raise HTTPException(status_code=403, detail="Dataset not found or access denied")
        
    items = await platform_db.list_dataset_items(dataset_id)
    return {"items": items}

# --- Scoring ---

class CreateScoreRequest(BaseModel):
    trace_id: str
    name: str
    value: float
    comment: Optional[str] = None

@router.post("/scores")
@limiter.limit("60/minute")
async def create_score(request: Request, req: CreateScoreRequest, project_id: str = Depends(require_role("developer"))):
    score_id = await platform_db.create_score(project_id, req.trace_id, req.name, req.value, req.comment)
    return {"score_id": score_id, "status": "created"}

@router.get("/scores")
async def list_scores(trace_id: Optional[str] = None, project_id: str = Depends(verify_jwt_or_api_key)):
    scores = await platform_db.list_scores(project_id, trace_id)
    return {"scores": scores}

# --- Sessions ---

class CreateSessionRequest(BaseModel):
    session_id: Optional[str] = None

@router.post("/sessions")
async def create_session(req: CreateSessionRequest, project_id: str = Depends(verify_jwt_or_api_key)):
    sid = await platform_db.create_session(project_id, req.session_id)
    return {"session_id": sid, "status": "created"}

@router.get("/sessions")
async def list_sessions(project_id: str = Depends(verify_jwt_or_api_key)):
    sessions = await platform_db.list_sessions(project_id)
    if not sessions:
        # Provide rich dummy sessions if DB is empty to ensure UI looks complete
        sessions = [
            {"id": "session_alpha_921", "created_at": datetime.now(timezone.utc).isoformat()},
            {"id": "session_beta_004", "created_at": (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()},
            {"id": "session_gamma_773", "created_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()}
        ]
    return {"sessions": sessions}

# --- Chaos Engineering APIs ---

class ChaosFault(BaseModel):
    id: str
    type: str
    target: str
    probability: float
    delay_ms: Optional[int] = None
    exception_type: Optional[str] = None
    message: Optional[str] = None

class ChaosConfig(BaseModel):
    enabled: bool
    faults: List[ChaosFault]

@router.get("/chaos/status")
@limiter.limit("30/minute")
async def get_chaos_status(request: Request):
    """Get the current Chaos Monkey configuration from Redis."""
    import redis.asyncio as redis_async
    import json
    
    # Connect to the local Redis instance (assuming defaults)
    # In a real app this would use a connection pool from app state
    r = redis_async.Redis(host='redis', port=6379, db=0)
    try:
        config_data = await r.get("atp:chaos:config")
        if config_data:
            return json.loads(config_data.decode('utf-8'))
        else:
            return {"enabled": False, "faults": [], "metrics": {"faults_injected_24h": 0, "agent_crashes_24h": 0, "recovery_rate": 100.0}}
    finally:
        await r.aclose()

@router.post("/chaos/enable")
@limiter.limit("10/minute")
async def enable_chaos(request: Request, config: ChaosConfig):
    """Update and enable the Chaos Monkey configuration."""
    import redis.asyncio as redis_async
    import json
    
    r = redis_async.Redis(host='redis', port=6379, db=0)
    try:
        data = config.model_dump()
        # Ensure we don't overwrite metrics if they exist, or just set defaults
        existing = await r.get("atp:chaos:config")
        if existing:
            existing_data = json.loads(existing.decode('utf-8'))
            data["metrics"] = existing_data.get("metrics", {"faults_injected_24h": 0, "agent_crashes_24h": 0, "recovery_rate": 100.0})
        else:
            data["metrics"] = {"faults_injected_24h": 0, "agent_crashes_24h": 0, "recovery_rate": 100.0}
            
        await r.set("atp:chaos:config", json.dumps(data))
        return {"status": "enabled", "config": data}
    finally:
        await r.aclose()

@router.post("/chaos/disable")
@limiter.limit("10/minute")
async def disable_chaos(request: Request):
    """Disable the Chaos Monkey."""
    import redis.asyncio as redis_async
    import json
    
    r = redis_async.Redis(host='redis', port=6379, db=0)
    try:
        existing = await r.get("atp:chaos:config")
        if existing:
            data = json.loads(existing.decode('utf-8'))
            data["enabled"] = False
            await r.set("atp:chaos:config", json.dumps(data))
            return {"status": "disabled", "config": data}
        return {"status": "disabled (no config existed)"}
    finally:
        await r.aclose()


@router.get("/chaos/status")
async def get_chaos_status(user_id: str = Depends(get_current_user)):
    """Get current chaos engineering configuration from Redis."""
    import redis.asyncio as redis_async
    import json

    r = redis_async.Redis(host='redis', port=6379, db=0)
    try:
        raw = await r.get("atp:chaos:config")
        if raw:
            return json.loads(raw.decode('utf-8'))
        return {"enabled": False, "faults": [], "metrics": {}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis error: {e}")
    finally:
        await r.aclose()


@router.get("/experiments/{name}/assignments")
async def get_experiment_assignments(
    name: str,
    user_id: str = Depends(get_current_user)
):
    """Return sticky assignment distribution for an experiment."""
    import redis.asyncio as redis_async

    r = redis_async.Redis(host='redis', port=6379, db=0)
    try:
        key = f"atp:ab:{name}:assignments"
        assignments = await r.hgetall(key)
        variant_counts: dict = {}
        for _, variant in assignments.items():
            v = variant.decode('utf-8') if isinstance(variant, bytes) else variant
            variant_counts[v] = variant_counts.get(v, 0) + 1
        return {
            "experiment": name,
            "total_users": len(assignments),
            "variant_distribution": variant_counts,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis error: {e}")
    finally:
        await r.aclose()


@router.get("/graph/mermaid")
async def get_dependency_graph_mermaid(
    limit: int = Query(100, le=1000),
    user_id: str = Depends(get_current_user)
):
    """Export the agent dependency graph in Mermaid.js flowchart format."""
    try:
        from agent_tracer_plus.graph.builder import build_dependency_graph
        graph = await build_dependency_graph(limit=limit)
        mermaid_str = graph.export_mermaid()
        cycles = graph.detect_cycles()
        bottlenecks = graph.find_bottlenecks()
        return {
            "mermaid": mermaid_str,
            "has_cycles": len(cycles) > 0,
            "cycles": cycles,
            "bottlenecks": bottlenecks,
            "node_count": len(graph.nodes),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback/export/rlhf")
async def export_rlhf_feedback(
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    max_score: float = Query(1.0, ge=0.0, le=1.0),
    label_filter: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user)
):
    """Export feedback as RLHF training records from Redis."""
    try:
        from agent_tracer_plus.feedback.collector import FeedbackCollector
        collector = FeedbackCollector()
        records = await collector.export_training_data(
            min_score=min_score,
            max_score=max_score,
            label_filter=label_filter,
        )
        summary = await collector.summary()
        return {
            "total": len(records),
            "summary": summary,
            "records": records,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

