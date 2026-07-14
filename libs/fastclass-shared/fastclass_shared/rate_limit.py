from __future__ import annotations

from dataclasses import dataclass

import redis.asyncio as redis
from fastapi import Request

from fastclass_shared.metrics import record_rate_limit_block


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"rate limited, retry after {retry_after_seconds}s")


@dataclass
class RateLimitRule:
    name: str
    limit: int
    window_seconds: int


class RedisRateLimiter:
    def __init__(self, *, redis_url: str, service_name: str, prefix: str = "rate-limit"):
        self.redis_url = redis_url
        self.service_name = service_name
        self.prefix = prefix

    async def hit(self, rule: RateLimitRule, *parts: str) -> None:
        key = ":".join([self.prefix, self.service_name, rule.name, *parts])
        client = redis.from_url(
            self.redis_url,
            decode_responses=True,
            max_connections=2,
        )
        try:
            current = await client.incr(key)
            if current == 1:
                await client.expire(key, rule.window_seconds)
            if current > rule.limit:
                ttl = await client.ttl(key)
                record_rate_limit_block(service=self.service_name, limiter=rule.name)
                raise RateLimitExceeded(retry_after_seconds=max(ttl, 1))
        finally:
            await client.aclose()


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
