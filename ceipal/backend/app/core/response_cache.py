"""Async response cache with optional Redis and in-process single-flight locks."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi.encoders import jsonable_encoder

from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_memory_cache: dict[str, dict[str, Any]] = {}
_locks: dict[str, asyncio.Lock] = {}
_redis_client: Any = None
_redis_checked = False


def _memory_get(key: str) -> Any | None:
    cached = _memory_cache.get(key)
    if not cached:
        return None
    if time.time() >= cached["expires_at"]:
        _memory_cache.pop(key, None)
        return None
    return cached["data"]


def _memory_set(key: str, data: Any, ttl: int) -> None:
    _memory_cache[key] = {"data": data, "expires_at": time.time() + ttl}


async def _get_redis() -> Any | None:
    global _redis_checked, _redis_client

    if not settings.redis_url:
        return None
    if _redis_checked:
        return _redis_client

    _redis_checked = True
    try:
        from redis.asyncio import Redis

        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        await _redis_client.ping()
        logger.info("Redis response cache enabled")
    except Exception as exc:
        _redis_client = None
        logger.warning("Redis response cache unavailable; using in-process cache: %s", exc)
    return _redis_client


async def cached_response(
    key: str,
    ttl: int,
    builder: Callable[[], Awaitable[Any]],
) -> Any:
    """Return cached JSON-compatible data and collapse concurrent rebuilds."""

    if ttl <= 0:
        return await builder()

    memory_hit = _memory_get(key)
    if memory_hit is not None:
        return memory_hit

    redis = await _get_redis()
    if redis is not None:
        cached = await redis.get(key)
        if cached:
            data = json.loads(cached)
            _memory_set(key, data, min(ttl, 30))
            return data

    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        memory_hit = _memory_get(key)
        if memory_hit is not None:
            return memory_hit

        redis = await _get_redis()
        if redis is not None:
            cached = await redis.get(key)
            if cached:
                data = json.loads(cached)
                _memory_set(key, data, min(ttl, 30))
                return data

            lock_key = f"lock:{key}"
            got_lock = await redis.set(lock_key, "1", nx=True, ex=60)
            if not got_lock:
                for _ in range(40):
                    await asyncio.sleep(0.25)
                    cached = await redis.get(key)
                    if cached:
                        data = json.loads(cached)
                        _memory_set(key, data, min(ttl, 30))
                        return data

            try:
                data = jsonable_encoder(await builder())
                _memory_set(key, data, ttl)
                jitter = random.randint(0, max(1, ttl // 10))
                await redis.set(key, json.dumps(data), ex=ttl + jitter)
                return data
            finally:
                if got_lock:
                    await redis.delete(lock_key)

        data = jsonable_encoder(await builder())
        _memory_set(key, data, ttl)

        return data


async def invalidate_prefix(prefix: str) -> None:
    """Best-effort invalidation for local memory and Redis keys."""

    for key in list(_memory_cache):
        if key.startswith(prefix):
            _memory_cache.pop(key, None)

    redis = await _get_redis()
    if redis is None:
        return

    async for key in redis.scan_iter(f"{prefix}*"):
        await redis.delete(key)
