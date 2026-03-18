"""
Simple in-memory cache with TTL.
Avoids hammering external APIs on every request.
"""

import time
from typing import Any, Optional

_cache: dict[str, dict] = {}

DEFAULT_TTL = 300  # 5 minutes


def get(key: str) -> Optional[Any]:
    """Return cached value if not expired, else None."""
    entry = _cache.get(key)
    if not entry:
        return None
    if time.time() > entry["expires_at"]:
        del _cache[key]
        return None
    return entry["value"]


def set(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    """Store value in cache with TTL in seconds."""
    _cache[key] = {
        "value": value,
        "expires_at": time.time() + ttl,
        "cached_at": time.time(),
    }


def invalidate(key: str) -> None:
    """Remove a single key from cache."""
    _cache.pop(key, None)


def clear_all() -> None:
    """Flush entire cache."""
    _cache.clear()


def stats() -> dict:
    """Return cache stats for debugging."""
    now = time.time()
    valid = {k: v for k, v in _cache.items() if v["expires_at"] > now}
    return {
        "total_keys": len(_cache),
        "valid_keys": len(valid),
        "keys": list(valid.keys()),
    }
