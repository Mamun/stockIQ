"""
Process-level cache abstraction.

CacheBackend — protocol that all cache implementations must satisfy.
MemoryCache  — in-process TTL dict (current default; shared across Streamlit sessions).

When splitting into a separate service, swap MemoryCache for a RedisCache
that implements the same protocol — no changes needed in decorated functions.

Usage:
    from stockiq.backend.cache import ttl_cache

    @ttl_cache(60)                           # default MemoryCache
    def my_fn(arg): ...

    _shared = MemoryCache()
    @ttl_cache(60, backend=_shared)          # inject a specific backend instance
    def another_fn(arg): ...
"""

import functools
import time
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CacheBackend(Protocol):
    """Minimal interface required by ttl_cache and future cache backends."""

    def get(self, key: str) -> tuple[Any, bool]:
        """Return (value, hit). hit=False means key missing or expired."""
        ...

    def set(self, key: str, value: Any, ttl: int) -> None:
        """Store value under key for ttl seconds."""
        ...

    def delete(self, key: str) -> None:
        """Remove a single key (no-op if absent)."""
        ...

    def clear(self) -> None:
        """Remove all entries."""
        ...


class MemoryCache:
    """In-process TTL cache backed by a plain dict.

    Each decorated function gets its own MemoryCache instance by default,
    so caches are isolated. Pass a shared instance to bridge two functions.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> tuple[Any, bool]:
        entry = self._store.get(key)
        if entry is None:
            return None, False
        value, expires = entry
        if time.time() < expires:
            return value, True
        del self._store[key]
        return None, False

    def set(self, key: str, value: Any, ttl: int) -> None:
        self._store[key] = (value, time.time() + ttl)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()


def ttl_cache(ttl_seconds: int, backend: CacheBackend | None = None):
    """Decorator that caches the return value for ``ttl_seconds`` seconds.

    Args:
        ttl_seconds: How long to keep cached values.
        backend: CacheBackend instance to use. Defaults to a new MemoryCache
                 per decorated function (isolated caches). Pass a shared
                 instance to group functions under one cache namespace.
    """
    def decorator(fn):
        _backend: CacheBackend = backend if backend is not None else MemoryCache()

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = str(args) + str(sorted(kwargs.items()))
            value, hit = _backend.get(key)
            if hit:
                return value
            result = fn(*args, **kwargs)
            _backend.set(key, result, ttl_seconds)
            return result

        wrapper.clear = _backend.clear  # type: ignore[attr-defined]
        return wrapper

    return decorator
