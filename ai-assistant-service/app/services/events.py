from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIAssistantEvent
from fastclass_shared.context import get_trace_id


async def emit_event(db: AsyncSession, *, event_type: str, payload: dict) -> AIAssistantEvent:
    if get_trace_id() and "_trace_id" not in payload:
        payload = {**payload, "_trace_id": get_trace_id()}
    event = AIAssistantEvent(event_type=event_type, payload=payload)
    db.add(event)
    await db.flush()
    return event


async def list_unpublished_events(db: AsyncSession, limit: int = 100) -> list[AIAssistantEvent]:
    result = await db.scalars(
        select(AIAssistantEvent)
        .where(AIAssistantEvent.published_at.is_(None))
        .order_by(AIAssistantEvent.created_at)
        .limit(limit)
    )
    return list(result.all())


async def mark_published(db: AsyncSession, event_ids: list) -> None:
    now = datetime.now(timezone.utc)
    events = await db.scalars(select(AIAssistantEvent).where(AIAssistantEvent.id.in_(event_ids)))
    for event in events:
        event.published_at = now
    await db.flush()
