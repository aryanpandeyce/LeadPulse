"""Async Redis client wrapper with graceful fallback for local/test environments."""

import logging
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class InMemoryRedisFallback:
    """Lightweight in-memory fallback used when Redis is unreachable in unit tests or offline dev."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}

    async def ping(self) -> bool:
        return True

    async def get(self, key: str) -> str | None:
        import time

        entry = self._store.get(key)
        if not entry:
            return None
        val, expires_at = entry
        if expires_at is not None and time.time() > expires_at:
            self._store.pop(key, None)
            return None
        return val

    async def set(
        self, key: str, value: str, ex: int | None = None, nx: bool = False
    ) -> bool:
        import time

        if nx:
            existing = await self.get(key)
            if existing is not None:
                return False
        expires_at = (time.time() + ex) if ex is not None else None
        self._store[key] = (value, expires_at)
        return True

    async def incr(self, key: str) -> int:
        current = await self.get(key)
        new_val = int(current or "0") + 1
        entry = self._store.get(key)
        expires_at = entry[1] if entry else None
        self._store[key] = (str(new_val), expires_at)
        return new_val

    async def expire(self, key: str, seconds: int) -> bool:
        import time

        entry = self._store.get(key)
        if not entry:
            return False
        self._store[key] = (entry[0], time.time() + seconds)
        return True

    async def ttl(self, key: str) -> int:
        import time

        entry = self._store.get(key)
        if not entry or entry[1] is None:
            return -1
        remaining = int(entry[1] - time.time())
        return max(1, remaining)

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self._store:
                self._store.pop(k, None)
                count += 1
        return count

    async def keys(self, pattern: str = "*") -> list[str]:
        import fnmatch

        return [k for k in list(self._store.keys()) if fnmatch.fnmatch(k, pattern)]


_redis_client: Any = None
_redis_loop: Any = None
_fallback_client = InMemoryRedisFallback()


async def close_redis() -> None:
    """Close cached Redis client (used on shutdown and between test event loops)."""
    global _redis_client, _redis_loop
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception:
            pass
        _redis_client = None
        _redis_loop = None


async def get_redis() -> Any:
    """Return an active async Redis client, or fallback in-memory store if unavailable."""
    import asyncio

    global _redis_client, _redis_loop
    current_loop = asyncio.get_running_loop()
    if _redis_client is not None and _redis_loop is current_loop:
        return _redis_client
    try:
        client: Any = aioredis.from_url(  # type: ignore[no-untyped-call]
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=1.0,
        )
        await asyncio.wait_for(client.ping(), timeout=0.8)
        _redis_client = client
        _redis_loop = current_loop
        return _redis_client
    except Exception:
        return _fallback_client

