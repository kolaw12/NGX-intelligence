"""Small in-memory TTL cache for local and single-process deployments."""

from __future__ import annotations

import copy
import logging
import time
from functools import wraps
from threading import RLock
from typing import Any, Callable, Hashable, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class TTLCache:
    """Thread-safe in-memory TTL cache.

    This is intentionally small and dependency-free. Production can replace it
    with Redis behind the same call sites when a shared cache is available.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._items: dict[Hashable, tuple[float, Any]] = {}
        self._lock = RLock()

    def get(self, key: Hashable) -> Any | None:
        now = time.monotonic()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                logger.debug("cache miss %s key=%r", self.name, key)
                return None
            expires_at, value = item
            if expires_at <= now:
                self._items.pop(key, None)
                logger.debug("cache expired %s key=%r", self.name, key)
                return None
            logger.debug("cache hit %s key=%r", self.name, key)
            return copy.deepcopy(value)

    def set(self, key: Hashable, value: Any, ttl_seconds: int) -> Any:
        with self._lock:
            self._items[key] = (time.monotonic() + ttl_seconds, copy.deepcopy(value))
        return value

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


def ttl_cache(ttl_seconds: int, name: str) -> Callable[[F], F]:
    """Cache a function result for a short fixed TTL."""

    cache = TTLCache(name)

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = _cache_key(args, kwargs)
            cached = cache.get(key)
            if cached is not None:
                return cached
            value = func(*args, **kwargs)
            return cache.set(key, value, ttl_seconds)

        wrapper.cache_clear = cache.clear  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


def _cache_key(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Hashable:
    return (
        tuple(_hashable(arg) for arg in args),
        tuple(sorted((key, _hashable(value)) for key, value in kwargs.items())),
    )


def _hashable(value: Any) -> Hashable:
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, (tuple, list)):
        return tuple(_hashable(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((str(key), _hashable(item)) for key, item in value.items()))
    return repr(value)
