"""
Redis-backed state store — survives gateway restarts.

Fallbacks to in-memory dicts if Redis is unavailable (graceful degradation).
"""

import json
import logging
from typing import Any, Optional

import redis

from .config import REDIS_URL

logger = logging.getLogger("state_store")

# ── Redis connection (lazy) ──────────────────────

_redis_client: Optional[redis.Redis] = None
_redis_available: bool | None = None  # None = not checked yet


def _get_redis() -> Optional[redis.Redis]:
    global _redis_client, _redis_available
    if _redis_available is False:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        _redis_client = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=2, socket_timeout=3)
        _redis_client.ping()
        _redis_available = True
        logger.info(f"[StateStore] Redis connected: {REDIS_URL}")
    except Exception as e:
        _redis_available = False
        _redis_client = None
        logger.warning(f"[StateStore] Redis unavailable ({e}), using in-memory fallback")
    return _redis_client


# ── In-memory fallback ──────────────────────────

_fallback_store: dict[str, Any] = {}
_fallback_expiry: dict[str, float] = {}


# ── Public API ──────────────────────────────────

KEY_PREFIX = "dzat:"
DEFAULT_TTL = 86400  # 24 hours


def get(key: str) -> Optional[Any]:
    """Get a value by key. Returns None if not found or expired."""
    r = _get_redis()
    full_key = f"{KEY_PREFIX}{key}"

    if r:
        try:
            raw = r.get(full_key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"[StateStore] Redis get error: {e}")
            # Fall through to fallback

    # In-memory fallback
    import time as _time
    if key in _fallback_store:
        expiry = _fallback_expiry.get(key)
        if expiry and _time.time() > expiry:
            del _fallback_store[key]
            _fallback_expiry.pop(key, None)
            return None
        return json.loads(json.dumps(_fallback_store[key]))  # deep copy
    return None


def set(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    """Set a value with optional TTL in seconds."""
    r = _get_redis()
    full_key = f"{KEY_PREFIX}{key}"
    serialized = json.dumps(value, ensure_ascii=False, default=str)

    if r:
        try:
            r.set(full_key, serialized, ex=ttl)
            return
        except Exception as e:
            logger.warning(f"[StateStore] Redis set error: {e}")

    # In-memory fallback
    _fallback_store[key] = json.loads(serialized)
    if ttl > 0:
        import time as _time
        _fallback_expiry[key] = _time.time() + ttl


def delete(key: str) -> None:
    """Delete a key."""
    r = _get_redis()
    full_key = f"{KEY_PREFIX}{key}"

    if r:
        try:
            r.delete(full_key)
        except Exception:
            pass

    _fallback_store.pop(key, None)
    _fallback_expiry.pop(key, None)


def hget(hash_name: str, field: str) -> Optional[Any]:
    """Get a field from a Redis hash (or fallback dict)."""
    r = _get_redis()
    full_hash = f"{KEY_PREFIX}{hash_name}"

    if r:
        try:
            raw = r.hget(full_hash, field)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            pass

    # In-memory fallback: use a nested dict
    fallback = _fallback_store.get(hash_name, {})
    return json.loads(json.dumps(fallback.get(field))) if field in fallback else None


def hset(hash_name: str, field: str, value: Any) -> None:
    """Set a field in a Redis hash (no TTL — persists indefinitely)."""
    r = _get_redis()
    full_hash = f"{KEY_PREFIX}{hash_name}"
    serialized = json.dumps(value, ensure_ascii=False, default=str)

    if r:
        try:
            r.hset(full_hash, field, serialized)
            return
        except Exception:
            pass

    # In-memory fallback
    if hash_name not in _fallback_store:
        _fallback_store[hash_name] = {}
    _fallback_store[hash_name][field] = json.loads(serialized)


def hdel(hash_name: str, field: str) -> None:
    """Delete a field from a Redis hash."""
    r = _get_redis()
    full_hash = f"{KEY_PREFIX}{hash_name}"

    if r:
        try:
            r.hdel(full_hash, field)
        except Exception:
            pass

    fallback = _fallback_store.get(hash_name, {})
    fallback.pop(field, None)


def hkeys(hash_name: str) -> list[str]:
    """Get all field names in a hash."""
    r = _get_redis()
    full_hash = f"{KEY_PREFIX}{hash_name}"

    if r:
        try:
            return [k.decode() if isinstance(k, bytes) else k for k in r.hkeys(full_hash)]
        except Exception:
            pass

    return list(_fallback_store.get(hash_name, {}).keys())


def scan_keys(pattern: str) -> list[str]:
    """Scan Redis for keys matching pattern. Slow — for debugging only."""
    r = _get_redis()
    full_pattern = f"{KEY_PREFIX}{pattern}"

    if r:
        try:
            keys = []
            for key in r.scan_iter(match=full_pattern, count=100):
                k = key.decode() if isinstance(key, bytes) else key
                keys.append(k.replace(KEY_PREFIX, "", 1))
            return keys
        except Exception:
            pass

    # In-memory fallback
    import fnmatch
    return [k for k in _fallback_store if fnmatch.fnmatch(k, pattern)]


def health_check() -> dict:
    """Return Redis connectivity status."""
    r = _get_redis()
    return {
        "redis_available": _redis_available or False,
        "redis_url": REDIS_URL,
        "storage": "redis" if _redis_available else "memory",
    }
