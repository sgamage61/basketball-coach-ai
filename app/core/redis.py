import json
from typing import Any

from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool

from app.core.config import get_settings

_pool: ConnectionPool | None = None


def get_redis_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
    return _pool


async def get_redis() -> Redis:  # type: ignore[type-arg]
    return Redis(connection_pool=get_redis_pool())


async def close_redis_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


class RedisCache:
    """Thin wrapper around Redis with JSON serialisation helpers."""

    def __init__(self, redis: Redis) -> None:  # type: ignore[type-arg]
        self._redis = redis

    async def get(self, key: str) -> Any | None:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        serialised = json.dumps(value, default=str)
        if ttl:
            await self._redis.setex(key, ttl, serialised)
        else:
            await self._redis.set(key, serialised)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self._redis.exists(key))

    async def publish(self, channel: str, message: Any) -> None:
        await self._redis.publish(channel, json.dumps(message, default=str))
