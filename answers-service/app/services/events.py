from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnswerEvent
from fastclass_shared.context import get_trace_id


async def emit_event(db: AsyncSession, *, event_type: str, payload: dict) -> AnswerEvent:
    if get_trace_id() and "_trace_id" not in payload:
        payload = {**payload, "_trace_id": get_trace_id()}
    event = AnswerEvent(event_type=event_type, payload=payload)
    db.add(event)
    await db.flush()
    return event


async def list_unpublished_events(db: AsyncSession, limit: int = 100) -> list[AnswerEvent]:
    result = await db.scalars(
        select(AnswerEvent)
        .where(AnswerEvent.published_at.is_(None))
        .order_by(AnswerEvent.created_at)
        .limit(limit)
    )
    return list(result.all())


async def mark_published(db: AsyncSession, event_ids: list) -> None:
    now = datetime.now(timezone.utc)
    events = await db.scalars(select(AnswerEvent).where(AnswerEvent.id.in_(event_ids)))
    for event in events:
        event.published_at = now
    await db.flush()
