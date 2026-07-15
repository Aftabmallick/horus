"""Production PostgreSQL Auth and Multi-tenancy Layer."""

import os
import secrets
import hashlib
import logging
import hmac
from typing import Optional
import bcrypt

import asyncpg

logger = logging.getLogger(__name__)

def hash_secret_key(secret_key: str) -> str:
    """Hash the secret key before storing it in the database."""
    return hashlib.sha256(secret_key.encode("utf-8")).hexdigest()

class PlatformDB:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        self.pool: Optional[asyncpg.Pool] = None

    async def init_pool(self):
        if not self.db_url:
            logger.warning("DATABASE_URL not set. Running in single-tenant local mode.")
            return
            
        self.pool = await asyncpg.create_pool(self.db_url)
        # Note: Schema migrations are managed by Alembic.
        # Run `alembic upgrade head` before starting the server.

    async def close_pool(self):
        if self.pool:
            await self.pool.close()

    async def generate_api_key(self, project_id: str):
        if not self.pool:
            return f"pk_{secrets.token_hex(8)}", f"sk_{secrets.token_hex(16)}"
            
        public_key = f"pk_{secrets.token_hex(8)}"
        secret_key = f"sk_{secrets.token_hex(16)}"
        secret_hash = hash_secret_key(secret_key)
        
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO api_keys (public_key, secret_hash, project_id) VALUES ($1, $2, $3)",
                public_key, secret_hash, project_id
            )
            
        return public_key, secret_key
        
    async def validate_api_key(self, public_key: str, secret_key: str) -> Optional[str]:
        """Returns project_id if valid, else None."""
        if not self.pool:
            # Fallback for local testing without Postgres
            if public_key == "pk_default" and secret_key == "sk_default":
                return "proj_default"
            return None
            
        secret_hash = hash_secret_key(secret_key)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT project_id, secret_hash FROM api_keys WHERE public_key = $1",
                public_key
            )
            if row and hmac.compare_digest(row["secret_hash"], secret_hash):
                return row["project_id"]
        return None

    async def create_user(self, email: str, password: str, org_id: str = "org_default", role: str = "viewer") -> Optional[str]:
        if not self.pool:
            return f"user_{secrets.token_hex(8)}"
            
        user_id = f"user_{secrets.token_hex(8)}"
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    "INSERT INTO users (id, email, password_hash, org_id, role) VALUES ($1, $2, $3, $4, $5)",
                    user_id, email, password_hash, org_id, role
                )
                return user_id
            except asyncpg.exceptions.UniqueViolationError:
                return None # Email already exists

    async def authenticate_user(self, email: str, password: str) -> Optional[dict]:
        if not self.pool:
            if email == "admin@demo.com" and password == "password":
                return {"id": "user_demo", "email": email, "org_id": "org_default", "role": "admin"}
            return None
            
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, password_hash, org_id, role FROM users WHERE email = $1",
                email
            )
            if row and bcrypt.checkpw(password.encode('utf-8'), row["password_hash"].encode('utf-8')):
                return {"id": row["id"], "email": row["email"], "org_id": row["org_id"], "role": row["role"]}
        return None

    # --- Prompts ---
    async def create_prompt(self, project_id: str, name: str, version: int, content: dict, branch: str = "main", parent_id: Optional[str] = None) -> str:
        if not self.pool: return f"prompt_{secrets.token_hex(8)}"
        prompt_id = f"prompt_{secrets.token_hex(8)}"
        import json
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO prompts (id, project_id, name, branch, version, parent_id, content) VALUES ($1, $2, $3, $4, $5, $6, $7)",
                prompt_id, project_id, name, branch, version, parent_id, json.dumps(content)
            )
        return prompt_id

    async def get_prompt(self, project_id: str, name: str, branch: str = "main", version: Optional[int] = None) -> Optional[dict]:
        if not self.pool: return None
        async with self.pool.acquire() as conn:
            if version is not None:
                row = await conn.fetchrow(
                    "SELECT id, name, branch, version, parent_id, content, created_at FROM prompts WHERE project_id = $1 AND name = $2 AND branch = $3 AND version = $4",
                    project_id, name, branch, version
                )
            else:
                row = await conn.fetchrow(
                    "SELECT id, name, branch, version, parent_id, content, created_at FROM prompts WHERE project_id = $1 AND name = $2 AND branch = $3 ORDER BY version DESC LIMIT 1",
                    project_id, name, branch
                )
            if row:
                import json
                return {
                    "id": row["id"], "name": row["name"], "branch": row["branch"], "version": row["version"], "parent_id": row["parent_id"],
                    "content": json.loads(row["content"]) if isinstance(row["content"], str) else row["content"], 
                    "created_at": row["created_at"].isoformat()
                }
        return None

    # --- Datasets ---
    async def create_dataset(self, project_id: str, name: str) -> str:
        if not self.pool: return f"ds_{secrets.token_hex(8)}"
        ds_id = f"ds_{secrets.token_hex(8)}"
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO datasets (id, project_id, name) VALUES ($1, $2, $3)",
                ds_id, project_id, name
            )
        return ds_id

    async def list_datasets(self, project_id: str) -> list:
        if not self.pool: return []
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, created_at FROM datasets WHERE project_id = $1 ORDER BY created_at DESC",
                project_id
            )
            return [{"id": r["id"], "name": r["name"], "created_at": r["created_at"].isoformat()} for r in rows]

    async def create_dataset_item(self, dataset_id: str, input_data: dict, expected_output: dict) -> str:
        if not self.pool: return f"item_{secrets.token_hex(8)}"
        item_id = f"item_{secrets.token_hex(8)}"
        import json
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO dataset_items (id, dataset_id, input, expected_output) VALUES ($1, $2, $3, $4)",
                item_id, dataset_id, json.dumps(input_data), json.dumps(expected_output)
            )
        return item_id

    async def list_dataset_items(self, dataset_id: str) -> list:
        if not self.pool: return []
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, input, expected_output, created_at FROM dataset_items WHERE dataset_id = $1 ORDER BY created_at ASC",
                dataset_id
            )
            import json
            def parse_json(val):
                return json.loads(val) if isinstance(val, str) else val
            return [{
                "id": r["id"], "input": parse_json(r["input"]), "expected_output": parse_json(r["expected_output"]),
                "created_at": r["created_at"].isoformat()
            } for r in rows]

    # --- Scores ---
    async def create_score(self, project_id: str, trace_id: str, name: str, value: float, comment: Optional[str] = None) -> str:
        if not self.pool: return f"score_{secrets.token_hex(8)}"
        score_id = f"score_{secrets.token_hex(8)}"
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO scores (id, project_id, trace_id, name, value, comment) VALUES ($1, $2, $3, $4, $5, $6)",
                score_id, project_id, trace_id, name, value, comment
            )
        return score_id

    async def list_scores(self, project_id: str, trace_id: Optional[str] = None) -> list:
        if not self.pool: return []
        async with self.pool.acquire() as conn:
            if trace_id:
                rows = await conn.fetch(
                    "SELECT id, trace_id, name, value, comment, created_at FROM scores WHERE project_id = $1 AND trace_id = $2 ORDER BY created_at DESC",
                    project_id, trace_id
                )
            else:
                rows = await conn.fetch(
                    "SELECT id, trace_id, name, value, comment, created_at FROM scores WHERE project_id = $1 ORDER BY created_at DESC",
                    project_id
                )
            return [{
                "id": r["id"], "trace_id": r["trace_id"], "name": r["name"], "value": float(r["value"]) if r["value"] is not None else None,
                "comment": r["comment"], "created_at": r["created_at"].isoformat()
            } for r in rows]

    # --- Sessions ---
    async def create_session(self, project_id: str, session_id: Optional[str] = None) -> str:
        if not self.pool: return session_id or f"sess_{secrets.token_hex(8)}"
        sid = session_id or f"sess_{secrets.token_hex(8)}"
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO sessions (id, project_id) VALUES ($1, $2) ON CONFLICT (id) DO NOTHING",
                sid, project_id
            )
        return sid

    async def list_sessions(self, project_id: str) -> list:
        if not self.pool: return []
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, created_at FROM sessions WHERE project_id = $1 ORDER BY created_at DESC",
                project_id
            )
            return [{"id": r["id"], "created_at": r["created_at"].isoformat()} for r in rows]

    # --- Experiments ---
    async def create_experiment(self, project_id: str, name: str, dataset_id: str, prompt_id: str) -> str:
        if not self.pool: return f"exp_{secrets.token_hex(8)}"
        exp_id = f"exp_{secrets.token_hex(8)}"
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO experiments (id, project_id, name, dataset_id, prompt_id) VALUES ($1, $2, $3, $4, $5)",
                exp_id, project_id, name, dataset_id, prompt_id
            )
        return exp_id

    async def get_experiment(self, project_id: str, exp_id: str) -> Optional[dict]:
        if not self.pool: return None
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, name, dataset_id, prompt_id, status, created_at FROM experiments WHERE project_id = $1 AND id = $2",
                project_id, exp_id
            )
            if row:
                return {"id": row["id"], "name": row["name"], "dataset_id": row["dataset_id"], "prompt_id": row["prompt_id"], "status": row["status"], "created_at": row["created_at"].isoformat()}
        return None

    async def list_experiments(self, project_id: str) -> list:
        if not self.pool: return []
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, dataset_id, prompt_id, status, created_at FROM experiments WHERE project_id = $1 ORDER BY created_at DESC",
                project_id
            )
            return [{"id": r["id"], "name": r["name"], "dataset_id": r["dataset_id"], "prompt_id": r["prompt_id"], "status": r["status"], "created_at": r["created_at"].isoformat()} for r in rows]

    async def create_experiment_result(self, experiment_id: str, dataset_item_id: str, output: dict, latency: float, cost: float, success: bool) -> str:
        if not self.pool: return f"res_{secrets.token_hex(8)}"
        res_id = f"res_{secrets.token_hex(8)}"
        import json
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO experiment_results (id, experiment_id, dataset_item_id, output, latency, cost, success) VALUES ($1, $2, $3, $4, $5, $6, $7)",
                res_id, experiment_id, dataset_item_id, json.dumps(output), latency, cost, success
            )
        return res_id

    async def list_experiment_results(self, experiment_id: str) -> list:
        if not self.pool: return []
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, dataset_item_id, output, latency, cost, success, created_at FROM experiment_results WHERE experiment_id = $1 ORDER BY created_at ASC",
                experiment_id
            )
            import json
            def parse_json(val):
                return json.loads(val) if isinstance(val, str) else val
            return [{
                "id": r["id"], "dataset_item_id": r["dataset_item_id"], "output": parse_json(r["output"]),
                "latency": float(r["latency"]) if r["latency"] is not None else 0,
                "cost": float(r["cost"]) if r["cost"] is not None else 0,
                "success": r["success"],
                "created_at": r["created_at"].isoformat()
            } for r in rows]

    # --- Trace Feedback ---
    async def create_trace_feedback(self, project_id: str, trace_id: str, rating: int, comment: Optional[str]) -> str:
        if not self.pool: return f"fb_{secrets.token_hex(8)}"
        fb_id = f"fb_{secrets.token_hex(8)}"
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO trace_feedback (id, trace_id, project_id, rating, comment) VALUES ($1, $2, $3, $4, $5)",
                fb_id, trace_id, project_id, rating, comment
            )
        return fb_id

    # --- Trace Annotations ---
    async def create_trace_annotation(self, project_id: str, trace_id: str, comment: str) -> str:
        if not self.pool: return f"ann_{secrets.token_hex(8)}"
        ann_id = f"ann_{secrets.token_hex(8)}"
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO trace_annotations (id, trace_id, project_id, comment) VALUES ($1, $2, $3, $4)",
                ann_id, trace_id, project_id, comment
            )
        return ann_id

    # --- Budgets ---
    async def set_budget(self, tenant_id: str, amount: float) -> dict:
        if not self.pool: return {"tenant_id": tenant_id, "amount": amount}
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO budgets (tenant_id, amount) VALUES ($1, $2) ON CONFLICT (tenant_id) DO UPDATE SET amount = EXCLUDED.amount, created_at = CURRENT_TIMESTAMP",
                tenant_id, amount
            )
        return {"tenant_id": tenant_id, "amount": amount}

    async def get_budget(self, tenant_id: str) -> Optional[float]:
        if not self.pool: return None
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT amount FROM budgets WHERE tenant_id = $1", tenant_id)
            if row:
                return float(row["amount"])
        return None

    # --- Alerts ---
    async def create_alert(self, project_id: str, name: str, condition: str, channel: str) -> str:
        if not self.pool: return f"alert_{secrets.token_hex(8)}"
        alert_id = f"alert_{secrets.token_hex(8)}"
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO alerts (id, project_id, name, condition, channel) VALUES ($1, $2, $3, $4, $5)",
                alert_id, project_id, name, condition, channel
            )
        return alert_id

    # --- Async Jobs ---
    async def create_async_job(self, project_id: str, job_type: str, trace_id: Optional[str] = None) -> str:
        if not self.pool: return f"{job_type}_{secrets.token_hex(8)}"
        job_id = f"{job_type}_{secrets.token_hex(8)}"
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO async_jobs (id, project_id, type, trace_id, status) VALUES ($1, $2, $3, $4, 'pending')",
                job_id, project_id, job_type, trace_id
            )
        return job_id

    async def get_async_job(self, project_id: str, job_id: str) -> Optional[dict]:
        if not self.pool: return None
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT id, type, status, result_data, created_at FROM async_jobs WHERE project_id = $1 AND id = $2", project_id, job_id)
            if row:
                import json
                return {
                    "id": row["id"], "type": row["type"], "status": row["status"], 
                    "result_data": json.loads(row["result_data"]) if row["result_data"] and isinstance(row["result_data"], str) else row["result_data"],
                    "created_at": row["created_at"].isoformat()
                }
        return None

    async def list_async_jobs(self, project_id: str, job_type: Optional[str] = None) -> list:
        if not self.pool: return []
        async with self.pool.acquire() as conn:
            if job_type:
                rows = await conn.fetch("SELECT id, type, status, created_at FROM async_jobs WHERE project_id = $1 AND type = $2 ORDER BY created_at DESC", project_id, job_type)
            else:
                rows = await conn.fetch("SELECT id, type, status, created_at FROM async_jobs WHERE project_id = $1 ORDER BY created_at DESC", project_id)
            return [{"id": r["id"], "type": r["type"], "status": r["status"], "created_at": r["created_at"].isoformat()} for r in rows]

platform_db = PlatformDB()
