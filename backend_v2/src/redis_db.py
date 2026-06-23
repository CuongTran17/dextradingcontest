"""
Optional Redis client with lazy connection and in-memory fallback.

Usage:
    from src.redis_db import get_redis, is_redis_available

    r = get_redis()
    if r:
        r.set("key", "value")
    else:
        # fall back to in-memory dict
        ...

If REDIS_URL is not set or Redis is unreachable, all calls to get_redis()
return None and the app continues with in-memory caches.
"""
import logging
import threading

from src.settings import get_settings

logger = logging.getLogger(__name__)

REDIS_URL = get_settings().redis_url

_pool = None
_client = None
_available: bool | None = None  # None = not yet probed
_probe_lock = threading.Lock()


def _probe() -> bool:
    """Try to create a connection pool and ping Redis once."""
    global _pool, _client, _available
    try:
        import redis

        _pool = redis.ConnectionPool.from_url(
            REDIS_URL,
            decode_responses=True,
            max_connections=20,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _client = redis.Redis(connection_pool=_pool)
        _client.ping()
        _available = True
        logger.info("Redis connected: %s", REDIS_URL)
    except Exception as exc:
        _available = False
        logger.warning(
            "Redis unavailable (%s). Running with in-memory cache only. "
            "Start Redis and restart the server to enable multi-worker sync.",
            exc,
        )
    return _available


def get_redis():
    """Return a Redis client, or None if Redis is not available."""
    global _available
    if _available is None:
        with _probe_lock:
            if _available is None:  # re-check after acquiring lock
                _probe()
    if not _available:
        return None
    return _client


def is_redis_available() -> bool:
    if _available is None:
        _probe()
    return bool(_available)
