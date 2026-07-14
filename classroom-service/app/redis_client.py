from collections.abc import AsyncIterator

import redis.asyncio as redis

from app.config import settings

redis_pool = redis.ConnectionPool.from_url(
    settings.redis_url,
    decode_responses=True,
    max_connections=2,
)


def get_redis_client() -> redis.Redis:
    return redis.Redis(connection_pool=redis_pool)


async def get_redis() -> AsyncIterator[redis.Redis]:
    client = get_redis_client()
    try:
        yield client
    finally:
        await client.aclose()
