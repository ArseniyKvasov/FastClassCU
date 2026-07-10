from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContentEvent
from fastclass_shared.context import get_trace_id


async def emit_event(db: AsyncSession, *, event_type: str, payload: dict) -> ContentEvent:
    """Call this in the same transaction as the change it describes - never
    after commit. That's what makes it a transactional outbox rather than a
    best-effort side call: either both the change and the event row land, or
    neither does."""
    if get_trace_id() and "_trace_id" not in payload:
        payload = {**payload, "_trace_id": get_trace_id()}
    event = ContentEvent(event_type=event_type, payload=payload)
    db.add(event)
    await db.flush()
    return event


async def list_unpublished_events(db: AsyncSession, limit: int = 100) -> list[ContentEvent]:
    """What an out-of-process relay (not implemented here - deployment picks
    its bus: Redis Streams, RabbitMQ, whatever) polls to forward events and
    then calls mark_published on. Kept as a plain poll rather than LISTEN/
    NOTIFY so it survives the relay being down for a while with nothing lost."""
    result = await db.scalars(
        select(ContentEvent)
        .where(ContentEvent.published_at.is_(None))
        .order_by(ContentEvent.created_at)
        .limit(limit)
    )
    return list(result.all())


async def mark_published(db: AsyncSession, event_ids: list) -> None:
    now = datetime.now(timezone.utc)
    events = await db.scalars(select(ContentEvent).where(ContentEvent.id.in_(event_ids)))
    for event in events:
        event.published_at = now
    await db.flush()
