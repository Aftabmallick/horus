import random
import time
import uuid
from locust import HttpUser, task, between

class AgentTracerLoadUser(HttpUser):
    wait_time = between(0.1, 1.0)
    
    @task(3)
    def submit_trace(self):
        """Simulate a trace representing a complex LangGraph execution."""
        trace_id = f"trace_{uuid.uuid4().hex}"
        project_id = "proj_default"
        
        # Simulate an Agent trace with 1 parent and 3 children (LLM, DB, Tool)
        payload = {
            "trace_id": trace_id,
            "project_id": project_id,
            "agent_name": "LangGraph_Support_Bot",
            "spans": [
                {
                    "span_id": f"span_{uuid.uuid4().hex}",
                    "name": "Support_Chain",
                    "span_type": "CHAIN",
                    "status": "OK",
                    "duration_ms": random.uniform(500, 3000),
                    "started_at": time.time(),
                },
                {
                    "span_id": f"span_{uuid.uuid4().hex}",
                    "parent_span_id": trace_id, # Simplified reference for load test
                    "name": "OpenAI_GPT_4",
                    "span_type": "LLM",
                    "status": "OK",
                    "duration_ms": random.uniform(300, 2500),
                    "token_usage": {
                        "input_tokens": random.randint(100, 500),
                        "output_tokens": random.randint(50, 200)
                    }
                }
            ]
        }
        
        # Assuming the API endpoint is /api/v1/traces
        self.client.post("/api/v1/traces", json=payload, headers={"Authorization": "Bearer sk_default"})

    @task(1)
    def fetch_dashboard(self):
        """Simulate a user loading the UI dashboard."""
        self.client.get("/api/v1/traces?limit=50", headers={"Authorization": "Bearer sk_default"})
