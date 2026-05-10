"""
Async Redis caching layer for API responses.
Uses redis.asyncio for non-blocking cache operations.
"""
import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

# Lazy-initialized client
_redis_client: Optional[aioredis.Redis] = None


def _get_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL, decode_responses=True
        )
    return _redis_client


async def get_cached(key: str) -> Optional[Any]:
    """Retrieve a JSON value from Redis. Returns None on miss or error."""
    try:
        client = _get_client()
        val = await client.get(key)
        if val:
            logger.debug(f"Cache HIT: {key}")
            return json.loads(val)
        logger.debug(f"Cache MISS: {key}")
        return None
    except Exception as e:
        logger.warning(f"Redis get error for {key}: {e}")
        return None


async def set_cached(key: str, value: Any, ttl: int = None) -> None:
    """Store a JSON-serialisable value in Redis with a TTL (seconds)."""
    if ttl is None:
        ttl = settings.REDIS_DEFAULT_TTL
    try:
        client = _get_client()
        await client.setex(key, ttl, json.dumps(value, default=str))
        logger.debug(f"Cache SET: {key} (TTL={ttl}s)")
    except Exception as e:
        logger.warning(f"Redis set error for {key}: {e}")


async def invalidate(pattern: str) -> None:
    """Delete one key or all keys matching a pattern (glob-style)."""
    try:
        client = _get_client()
        if "*" in pattern:
            keys = []
            async for key in client.scan_iter(match=pattern, count=100):
                keys.append(key)
            if keys:
                await client.delete(*keys)
                logger.debug(f"Cache INVALIDATED {len(keys)} keys matching {pattern}")
        else:
            await client.delete(pattern)
            logger.debug(f"Cache INVALIDATED: {pattern}")
    except Exception as e:
        logger.warning(f"Redis invalidate error for {pattern}: {e}")
