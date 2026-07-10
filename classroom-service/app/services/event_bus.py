import asyncio
import uuid

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.db import SessionLocal
from app.models import ConsumedEvent
from app.services import events as events_svc
from app.services import membership as membership_svc
from fastclass_shared.events import ConsumerConfig, EventEnvelope, RelayConfig, run_consumer_loop, run_relay_loop

CONSUMER_NAME = "classroom-service.auth-user-upgraded"


def _event_bus_client() -> redis.Redis:
    return redis.from_url(settings.event_bus_redis_url, decode_responses=True)


async def _list_unpublished_events(limit: int):
    async with SessionLocal() as db:
        return await events_svc.list_unpublished_events(db, limit)


async def _mark_published(event_ids: list) -> None:
    async with SessionLocal() as db:
        await events_svc.mark_published(db, event_ids)
        await db.commit()


async def _is_processed(event_id: str) -> bool:
    async with SessionLocal() as db:
        existing = await db.scalar(
            select(ConsumedEvent).where(
                ConsumedEvent.event_id == event_id,
                ConsumedEvent.consumer_name == CONSUMER_NAME,
            )
        )
        return existing is not None


async def _mark_processed(event_id: str) -> None:
    async with SessionLocal() as db:
        db.add(ConsumedEvent(event_id=event_id, consumer_name=CONSUMER_NAME))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()


async def _handle_auth_event(envelope: EventEnvelope) -> None:
    if envelope.event_type != "user_upgraded":
        return
    old_user_id = uuid.UUID(envelope.payload["old_guest_session_id"])
    new_user_id = uuid.UUID(envelope.payload["new_user_id"])
    async with SessionLocal() as db:
        await membership_svc.apply_user_upgraded(
            db,
            old_user_id=old_user_id,
            new_user_id=new_user_id,
        )
        await db.commit()


async def run(stop_event: asyncio.Event) -> None:
    client = _event_bus_client()
    relay_task = asyncio.create_task(
        run_relay_loop(
            r=client,
            config=RelayConfig(producer_name="classroom-service"),
            list_unpublished_events=_list_unpublished_events,
            mark_published=_mark_published,
            stop_event=stop_event,
        )
    )
    consumer_task = asyncio.create_task(
        run_consumer_loop(
            r=client,
            config=ConsumerConfig(
                consumer_name=CONSUMER_NAME,
                stream_producer="auth-service",
                group_name="classroom-service",
            ),
            handler=_handle_auth_event,
            is_processed=_is_processed,
            mark_processed=_mark_processed,
            stop_event=stop_event,
        )
    )
    try:
        await asyncio.gather(relay_task, consumer_task)
    finally:
        for task in (relay_task, consumer_task):
            task.cancel()
        await client.aclose()
