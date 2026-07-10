import json
import uuid

import redis.asyncio as redis


def channel_name(assignment_id: uuid.UUID) -> str:
    return f"assignment:{assignment_id}"


async def publish(r: redis.Redis, *, assignment_id: uuid.UUID, message: dict) -> None:
    """Same rule as Classroom Service: every delivery goes through Redis
    pub/sub, no in-process shortcut - this is deliberately the ONLY
    mechanism, kept intentionally simple (no chat, no presence, no observed-
    student state - just notifications) per the product ask for this
    service's WS to be as simple as possible."""
    await r.publish(channel_name(assignment_id), json.dumps(message))
