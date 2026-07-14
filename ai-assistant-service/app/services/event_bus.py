import asyncio

import redis.asyncio as redis

from app.config import settings
from app.db import get_session_factory
from app.services import events as events_svc
from fastclass_shared.events import RelayConfig, run_relay_loop


def _event_bus_client() -> redis.Redis:
    return redis.from_url(
        settings.event_bus_redis_url,
        decode_responses=True,
        max_connections=2,
    )


async def _list_unpublished_events(limit: int):
    async with get_session_factory()() as db:
        return await events_svc.list_unpublished_events(db, limit)


async def _mark_published(event_ids: list) -> None:
    async with get_session_factory()() as db:
        await events_svc.mark_published(db, event_ids)
        await db.commit()


async def run(stop_event: asyncio.Event) -> None:
    client = _event_bus_client()
    try:
        await run_relay_loop(
            r=client,
            config=RelayConfig(producer_name="ai-assistant-service"),
            list_unpublished_events=_list_unpublished_events,
            mark_published=_mark_published,
            stop_event=stop_event,
        )
    finally:
        await client.aclose()
