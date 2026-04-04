# cache.py
import redis
import json
import logging
from typing import Any, Optional
from config import settings

logger = logging.getLogger(__name__)

# ── Connection ────────────────────────────────────────────────
def _create_client():
    try:
        client = redis.from_url(
            settings.redis_url,
            decode_responses=True,        # always get str back, not bytes
            socket_connect_timeout=3,     # fail fast if Upstash unreachable
            socket_timeout=3,
            retry_on_timeout=True,
        )
        client.ping()
        logger.info("✅ Redis cache connected")
        return client
    except Exception as e:
        logger.warning(f"⚠️ Redis unavailable — cache disabled: {e}")
        return None

_client = _create_client()

# ── TTL Constants (seconds) ───────────────────────────────────
TTL_COURSES_LIST  = 120   # course list       → 2 min
TTL_COURSE_DETAIL = 180   # single course     → 3 min
TTL_NOTIFICATIONS = 30    # notifications     → 30 sec
TTL_CALENDAR      = 300   # conference cal    → 5 min

# ── Core Functions ────────────────────────────────────────────
def cache_get(key: str) -> Optional[Any]:
    """Get a value from cache. Returns None if missing or Redis is down."""
    if _client is None:
        return None
    try:
        value = _client.get(key)
        if value is None:
            return None
        return json.loads(value)
    except Exception as e:
        logger.warning(f"cache_get error ({key}): {e}")
        return None


def cache_set(key: str, value: Any, ttl: int = 60) -> None:
    """Store a value in cache. Silently skips if Redis is down."""
    if _client is None:
        return
    try:
        _client.setex(key, ttl, json.dumps(value, default=str))
    except Exception as e:
        logger.warning(f"cache_set error ({key}): {e}")


def cache_delete(key: str) -> None:
    """Delete a single key."""
    if _client is None:
        return
    try:
        _client.delete(key)
    except Exception as e:
        logger.warning(f"cache_delete error ({key}): {e}")


def cache_delete_pattern(prefix: str) -> None:
    """Delete all keys matching prefix* — used for invalidation."""
    if _client is None:
        return
    try:
        # SCAN is safe for production (non-blocking unlike KEYS)
        cursor = 0
        while True:
            cursor, keys = _client.scan(cursor, match=f"{prefix}*", count=100)
            if keys:
                _client.delete(*keys)
            if cursor == 0:
                break
    except Exception as e:
        logger.warning(f"cache_delete_pattern error ({prefix}): {e}")


def cache_stats() -> dict:
    """Returns cache info — used by admin endpoint."""
    if _client is None:
        return {"status": "disabled", "reason": "Redis unavailable"}
    try:
        info = _client.info()
        return {
            "status": "connected",
            "used_memory_human": info.get("used_memory_human"),
            "connected_clients": info.get("connected_clients"),
            "total_commands_processed": info.get("total_commands_processed"),
            "keyspace_hits": info.get("keyspace_hits"),
            "keyspace_misses": info.get("keyspace_misses"),
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    
