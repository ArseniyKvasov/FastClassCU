import uuid

import redis.asyncio as redis

from app.config import settings

_PREFIX = "presence"


def _key(classroom_id: uuid.UUID, user_id: uuid.UUID, connection_id: str) -> str:
    return f"{_PREFIX}:{classroom_id}:{user_id}:{connection_id}"


def _ttl_seconds() -> int:
    # Generous relative to the heartbeat interval - a couple of missed
    # heartbeats shouldn't flip someone to "offline" (see socket hub: the
    # connection itself tolerates ws_heartbeat_missed_limit misses before
    # closing; presence TTL should outlive that, not race it).
    return settings.ws_heartbeat_interval_seconds * (settings.ws_heartbeat_missed_limit + 1)


async def mark_online(
    r: redis.Redis, *, classroom_id: uuid.UUID, user_id: uuid.UUID, connection_id: str
) -> None:
    """Call on connect AND on every heartbeat - this key IS the presence
    state, no separate in-process bookkeeping. If a connection dies without
    a clean disconnect, the key simply expires - no explicit cleanup needed,
    which is what makes this safe across worker crashes/restarts."""
    await r.set(_key(classroom_id, user_id, connection_id), "1", ex=_ttl_seconds())


async def mark_offline(
    r: redis.Redis, *, classroom_id: uuid.UUID, user_id: uuid.UUID, connection_id: str
) -> None:
    await r.delete(_key(classroom_id, user_id, connection_id))


async def list_online(r: redis.Redis, *, classroom_id: uuid.UUID) -> list[uuid.UUID]:
    pattern = f"{_PREFIX}:{classroom_id}:*"
    user_ids: set[uuid.UUID] = set()
    async for key in r.scan_iter(match=pattern, count=100):
        # key shape: presence:{classroom_id}:{user_id}:{connection_id}
        parts = key.split(":")
        user_ids.add(uuid.UUID(parts[2]))
    return list(user_ids)


async def is_online(r: redis.Redis, *, classroom_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    pattern = f"{_PREFIX}:{classroom_id}:{user_id}:*"
    async for _ in r.scan_iter(match=pattern, count=10):
        return True
    return False
