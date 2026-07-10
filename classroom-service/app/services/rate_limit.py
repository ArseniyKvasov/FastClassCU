import uuid

import redis.asyncio as redis

from app.config import settings
from fastclass_shared import RateLimitExceeded, RateLimitRule, RedisRateLimiter

_limiter = RedisRateLimiter(
    redis_url=settings.rate_limit_redis_url,
    service_name="classroom-service",
    prefix="join",
)


async def check_join_lockout(r: redis.Redis, *, classroom_id: uuid.UUID) -> None:
    """Second layer, on top of per-IP limiting: if a classroom has seen too
    many failed join attempts in aggregate (any mix of source IPs), lock out
    ALL join attempts for it for a cooldown period. This is what a per-IP-only
    limiter (the old system's design) can't defend against - a distributed
    attempt spread across many IPs each staying under their own budget."""
    locked = await r.get(f"join:lockout:{classroom_id}")
    if locked:
        ttl = await r.ttl(f"join:lockout:{classroom_id}")
        raise RateLimitExceeded(retry_after_seconds=max(ttl, 1))


async def record_join_attempt(
    r: redis.Redis, *, classroom_id: uuid.UUID, client_ip: str
) -> None:
    """Counts every attempt (right or wrong password) against both budgets -
    call this BEFORE checking the password, so a flood of attempts is capped
    regardless of whether any of them happen to be correct."""
    await _limiter.hit(
        RateLimitRule(
            name="ip",
            limit=settings.join_attempts_per_ip_limit,
            window_seconds=settings.join_attempts_per_ip_window_seconds,
        ),
        str(classroom_id),
        client_ip,
    )
    try:
        await _limiter.hit(
            RateLimitRule(
                name="global",
                limit=settings.join_attempts_global_per_classroom_limit,
                window_seconds=settings.join_attempts_global_per_classroom_window_seconds,
            ),
            str(classroom_id),
        )
    except RateLimitExceeded:
        await r.set(
            f"join:lockout:{classroom_id}", "1", ex=settings.join_lockout_seconds
        )
        raise
