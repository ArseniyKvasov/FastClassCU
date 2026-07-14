import asyncio
import uuid

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.db import SessionLocal
from app.models import ConsumedEvent
from app.redis_client import get_redis_client
from app.services import events as events_svc
from app.services import grading as grading_svc
from app.ws.manager import publish
from fastclass_shared.events import ConsumerConfig, EventEnvelope, RelayConfig, run_consumer_loop, run_relay_loop

CONSUMER_NAME = "assignments-service.answers-answer-scored"


def _event_bus_client() -> redis.Redis:
    return redis.from_url(
        settings.event_bus_redis_url,
        decode_responses=True,
        max_connections=2,
    )


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


async def _handle_answers_event(envelope: EventEnvelope) -> None:
    if envelope.event_type != "answer_scored":
        return
    async with SessionLocal() as db:
        session = await grading_svc.apply_answer_scored(
            db,
            session_id=uuid.UUID(envelope.payload["session_id"]),
            task_id=uuid.UUID(envelope.payload["task_id"]),
            correctness=float(envelope.payload["correctness"]),
        )
        await db.commit()

    if session is None or session.grade is None:
        return

    redis_client = get_redis_client()
    try:
        await publish(
            redis_client,
            assignment_id=session.assignment_id,
            message={
                "type": "session_grade_changed",
                "session_id": str(session.id),
                "grade": float(session.grade),
            },
        )
    finally:
        await redis_client.aclose()


async def run(stop_event: asyncio.Event) -> None:
    client = _event_bus_client()
    relay_task = asyncio.create_task(
        run_relay_loop(
            r=client,
            config=RelayConfig(producer_name="assignments-service"),
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
                stream_producer="answers-service",
                group_name="assignments-service",
            ),
            handler=_handle_answers_event,
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
