import json
import uuid

import redis.asyncio as redis


def channel_name(classroom_id: uuid.UUID) -> str:
    return f"classroom:{classroom_id}"


async def publish(r: redis.Redis, *, classroom_id: uuid.UUID, message: dict) -> None:
    """The ONLY way messages reach connected clients - every delivery goes
    through Redis pub/sub, with no in-process shortcut. This is deliberately
    slightly slower than a direct in-memory dict lookup (the old system's
    approach for `draw`/`text:op`) in exchange for correctness across worker
    processes: any worker holding a relevant connection gets the message,
    not just the one that happened to originate it."""
    await r.publish(channel_name(classroom_id), json.dumps(message))
