"""Traffic assignment."""

import hashlib
import json
import logging
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    redis = None

_redis_client = None

def get_redis_client():
    global _redis_client
    if not HAS_REDIS:
        return None
    if _redis_client is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.from_url(url)
    return _redis_client

async def assign_variant(user_id: str, experiment_name: str, variants: list[str], traffic_split: list[float]) -> str:
    """Deterministically assign a user to a variant with Redis persistence."""
    redis_key = f"atp:ab:{experiment_name}:assignments"
    client = get_redis_client()

    if client:
        try:
            cached = await client.hget(redis_key, user_id)
            if cached:
                return cached.decode('utf-8')
        except Exception as e:
            logger.warning(f"Redis hget failed: {e}")

    # Deterministic fallback via hash
    h = int(hashlib.md5(f"{user_id}:{experiment_name}".encode('utf-8')).hexdigest(), 16)
    cumulative = 0.0
    assigned = variants[-1]
    
    for variant, split in zip(variants, traffic_split):
        cumulative += split
        if (h % 10000) / 10000.0 < cumulative:
            assigned = variant
            break

    if client:
        try:
            await client.hset(redis_key, user_id, assigned)
            # 90-day TTL for sticky assignment
            await client.expire(redis_key, 60 * 60 * 24 * 90)
        except Exception as e:
            logger.warning(f"Redis hset failed: {e}")

    return assigned
