import asyncio

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.db import SessionLocal
from app.models import ConsumedEvent
from app.services import projections
from fastclass_shared.events import ConsumerConfig, EventEnvelope, run_consumer_loop

CONSUMERS = (
    ConsumerConfig(
        consumer_name="analytics-service.auth",
        stream_producer="auth-service",
        group_name="analytics-service",
    ),
    ConsumerConfig(
        consumer_name="analytics-service.content",
        stream_producer="content-service",
        group_name="analytics-service",
    ),
    ConsumerConfig(
        consumer_name="analytics-service.classroom",
        stream_producer="classroom-service",
        group_name="analytics-service",
    ),
    ConsumerConfig(
        consumer_name="analytics-service.assignments",
        stream_producer="assignments-service",
        group_name="analytics-service",
    ),
    ConsumerConfig(
        consumer_name="analytics-service.answers",
        stream_producer="answers-service",
        group_name="analytics-service",
    ),
    ConsumerConfig(
        consumer_name="analytics-service.ai-assistant",
        stream_producer="ai-assistant-service",
        group_name="analytics-service",
    ),
)


def _event_bus_client() -> redis.Redis:
    return redis.from_url(
        settings.event_bus_redis_url,
        decode_responses=True,
        max_connections=2,
    )


def _is_processed_factory(consumer_name: str):
    async def _is_processed(event_id: str) -> bool:
        async with SessionLocal() as db:
            existing = await db.scalar(
                select(ConsumedEvent).where(
                    ConsumedEvent.event_id == event_id,
                    ConsumedEvent.consumer_name == consumer_name,
                )
            )
            return existing is not None

    return _is_processed


def _mark_processed_factory(consumer_name: str):
    async def _mark_processed(event_id: str) -> None:
        async with SessionLocal() as db:
            db.add(ConsumedEvent(event_id=event_id, consumer_name=consumer_name))
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()

    return _mark_processed


async def _handle_event(envelope: EventEnvelope) -> None:
    async with SessionLocal() as db:
        await projections.apply_event(db, envelope)


async def run(stop_event: asyncio.Event) -> None:
    client = _event_bus_client()
    tasks = [
        asyncio.create_task(
            run_consumer_loop(
                r=client,
                config=config,
                handler=_handle_event,
                is_processed=_is_processed_factory(config.consumer_name),
                mark_processed=_mark_processed_factory(config.consumer_name),
                stop_event=stop_event,
            )
        )
        for config in CONSUMERS
    ]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await client.aclose()
