"""
Sync Redis client with lazy connection and graceful in-memory fallback.

Usage:
    from src.database.redis_db import get_redis

    r = get_redis()
    if r:
        r.set("key", "value")
    else:
        # fall back to in-memory dict
        ...

If REDIS_URL is not set or Redis is unreachable, get_redis() returns None
and the app continues with in-memory caches.
"""
import logging
import threading

from src.settings import get_settings

logger = logging.getLogger(__name__)

REDIS_URL = get_settings().redis_url

_client = None
_available: bool | None = None
_probe_lock = threading.Lock()


def _probe() -> None:
    global _client, _available
    try:
        import redis

        pool = redis.ConnectionPool.from_url(
            REDIS_URL,
            decode_responses=True,
            max_connections=20,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        c = redis.Redis(connection_pool=pool)
        c.ping()
        _client = c
        _available = True
        logger.info("Redis connected: %s", REDIS_URL)
    except Exception as exc:
        _available = False
        logger.warning(
            "Redis unavailable (%s). Running with in-memory cache only. "
            "Start Redis and restart the server to enable multi-worker sync.",
            exc,
        )


def get_redis():
    """Return a connected sync Redis client, or None if Redis is unavailable."""
    global _available
    if _available is None:
        with _probe_lock:
            if _available is None:
                _probe()
    return _client if _available else None


def is_redis_available() -> bool:
    if _available is None:
        with _probe_lock:
            if _available is None:
                _probe()
    return bool(_available)


def check_redis_health() -> bool:
    r = get_redis()
    if r is None:
        return False
    try:
        r.ping()
        return True
    except Exception as exc:
        logger.error("Redis health check failed: %s", exc)
        return False


class _LazyRedis:
    """
    Transparent proxy so `from src.database.redis_db import redis_client` works.
    Evaluates as falsy when Redis is unavailable — existing `if not redis_client:`
    guards take the in-memory fallback path without any code changes at call sites.
    """

    def __bool__(self) -> bool:
        return get_redis() is not None

    def __getattr__(self, name: str):
        r = get_redis()
        if r is None:
            raise RuntimeError(f"Redis not available (tried .{name})")
        return getattr(r, name)


redis_client = _LazyRedis()
