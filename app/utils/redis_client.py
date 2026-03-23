"""
Redis client singleton.

Used by:
  - Idempotency key caching (orders)
  - Dashboard cache (admin)
  - Reservation expiry tracking

Call get_redis() to get a connected redis.Redis instance.
The connection is created once at module level and reused across requests.
"""
import redis
from app.core.config import settings

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return the module-level Redis client, creating it if necessary."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=False,  # bytes for general use; callers decode as needed
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=True,
        )
    return _redis_client


def get_redis_text() -> redis.Redis:
    """
    Return a Redis client with decode_responses=True for string-only use
    (e.g. dashboard cache where JSON strings are stored/retrieved).
    """
    return redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
        retry_on_timeout=True,
    )
