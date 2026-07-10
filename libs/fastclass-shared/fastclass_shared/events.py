from __future__ import annotations

import asyncio
import json
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

import redis.asyncio as redis
from pydantic import BaseModel, Field

from fastclass_shared.context import clear_context, get_request_id, set_request_id, set_trace_context
from fastclass_shared.metrics import (
    record_event_bus_failure,
    record_event_consumed,
    record_event_published,
    set_outbox_backlog,
)

logger = logging.getLogger("fastclass.events")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventEnvelope(BaseModel):
    event_id: str
    event_type: str
    occurred_at: str
    producer: str
    schema_version: int = 1
    trace_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


@dataclass
class RelayConfig:
    producer_name: str
    batch_size: int = 100
    poll_interval_seconds: float = 2.0


@dataclass
class ConsumerConfig:
    consumer_name: str
    stream_producer: str
    group_name: str
    read_count: int = 10
    block_ms: int = 2000


def stream_name(producer_name: str) -> str:
    return f"events.{producer_name}"


def build_envelope(*, producer_name: str, event_row: Any) -> EventEnvelope:
    occurred_at = getattr(event_row, "created_at", None)
    if isinstance(occurred_at, datetime):
        occurred_at_raw = occurred_at.astimezone(timezone.utc).isoformat()
    else:
        occurred_at_raw = _utc_now_iso()

    payload = dict(getattr(event_row, "payload", {}) or {})
    event_id = str(getattr(event_row, "id", "") or uuid.uuid4())
    trace_id = payload.pop("_trace_id", None)

    return EventEnvelope(
        event_id=event_id,
        event_type=str(getattr(event_row, "event_type", "unknown")),
        occurred_at=occurred_at_raw,
        producer=producer_name,
        trace_id=trace_id,
        payload=payload,
    )


async def publish_envelope(r: redis.Redis, envelope: EventEnvelope) -> str:
    return await r.xadd(
        stream_name(envelope.producer),
        {"envelope": envelope.model_dump_json()},
        maxlen=10_000,
        approximate=True,
    )


async def ensure_consumer_group(
    r: redis.Redis, *, producer_name: str, group_name: str
) -> None:
    stream = stream_name(producer_name)
    try:
        await r.xgroup_create(stream, group_name, id="0", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def relay_once(
    *,
    r: redis.Redis,
    config: RelayConfig,
    list_unpublished_events: Callable[[int], Awaitable[list[Any]]],
    mark_published: Callable[[list[Any]], Awaitable[None]],
) -> int:
    events = await list_unpublished_events(config.batch_size)
    set_outbox_backlog(producer=config.producer_name, backlog=len(events))
    if not events:
        return 0

    published_ids: list[Any] = []
    for event_row in events:
        envelope = build_envelope(producer_name=config.producer_name, event_row=event_row)
        await publish_envelope(r, envelope)
        record_event_published(producer=config.producer_name, event_type=envelope.event_type)
        published_ids.append(getattr(event_row, "id"))
    await mark_published(published_ids)
    return len(published_ids)


async def run_relay_loop(
    *,
    r: redis.Redis,
    config: RelayConfig,
    list_unpublished_events: Callable[[int], Awaitable[list[Any]]],
    mark_published: Callable[[list[Any]], Awaitable[None]],
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            count = await relay_once(
                r=r,
                config=config,
                list_unpublished_events=list_unpublished_events,
                mark_published=mark_published,
            )
            if count == 0:
                await asyncio.wait_for(stop_event.wait(), timeout=config.poll_interval_seconds)
        except TimeoutError:
            continue
        except Exception:
            logger.exception("relay_loop_failed", extra={"producer": config.producer_name})
            record_event_bus_failure(role="relay", name=config.producer_name)
            await asyncio.sleep(config.poll_interval_seconds)


async def consume_once(
    *,
    r: redis.Redis,
    config: ConsumerConfig,
    handler: Callable[[EventEnvelope], Awaitable[None]],
    is_processed: Callable[[str], Awaitable[bool]],
    mark_processed: Callable[[str], Awaitable[None]],
) -> int:
    response = await r.xreadgroup(
        groupname=config.group_name,
        consumername=config.consumer_name,
        streams={stream_name(config.stream_producer): ">"},
        count=config.read_count,
        block=config.block_ms,
    )
    if not response:
        return 0

    processed = 0
    for _stream, entries in response:
        for message_id, fields in entries:
            raw = fields.get("envelope")
            if raw is None:
                await r.xack(stream_name(config.stream_producer), config.group_name, message_id)
                continue

            envelope = EventEnvelope.model_validate_json(raw)
            if await is_processed(envelope.event_id):
                await r.xack(stream_name(config.stream_producer), config.group_name, message_id)
                record_event_consumed(
                    consumer=config.consumer_name,
                    producer=config.stream_producer,
                    event_type=envelope.event_type,
                    status="duplicate",
                )
                processed += 1
                continue

            try:
                set_request_id(envelope.event_id)
                set_trace_context(trace_id=envelope.trace_id, span_id=secrets.token_hex(8))
                await handler(envelope)
                await mark_processed(envelope.event_id)
                await r.xack(stream_name(config.stream_producer), config.group_name, message_id)
                record_event_consumed(
                    consumer=config.consumer_name,
                    producer=config.stream_producer,
                    event_type=envelope.event_type,
                    status="processed",
                )
                processed += 1
            finally:
                clear_context()
    return processed


async def run_consumer_loop(
    *,
    r: redis.Redis,
    config: ConsumerConfig,
    handler: Callable[[EventEnvelope], Awaitable[None]],
    is_processed: Callable[[str], Awaitable[bool]],
    mark_processed: Callable[[str], Awaitable[None]],
    stop_event: asyncio.Event,
) -> None:
    await ensure_consumer_group(
        r,
        producer_name=config.stream_producer,
        group_name=config.group_name,
    )
    while not stop_event.is_set():
        try:
            await consume_once(
                r=r,
                config=config,
                handler=handler,
                is_processed=is_processed,
                mark_processed=mark_processed,
            )
        except Exception:
            logger.exception(
                "consumer_loop_failed",
                extra={
                    "producer": config.stream_producer,
                    "group": config.group_name,
                    "consumer": config.consumer_name,
                },
            )
            record_event_bus_failure(role="consumer", name=config.consumer_name)
            await asyncio.sleep(1.0)
