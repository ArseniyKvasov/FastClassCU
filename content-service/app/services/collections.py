import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LessonCollection, LessonCollectionItem, LessonQualityFeedback
from app.services.events import emit_event


async def create_collection(
    db: AsyncSession,
    *,
    owner_id: uuid.UUID,
    title: str,
    description: str | None = None,
    is_sequential: bool = False,
) -> LessonCollection:
    collection = LessonCollection(
        owner_id=owner_id, title=title, description=description, is_sequential=is_sequential
    )
    db.add(collection)
    await db.flush()
    return collection


async def list_collections_for_owner(
    db: AsyncSession, *, owner_id: uuid.UUID
) -> list[LessonCollection]:
    result = await db.scalars(
        select(LessonCollection).where(LessonCollection.owner_id == owner_id)
    )
    return list(result.all())


async def add_lesson_to_collection(
    db: AsyncSession, *, collection_id: uuid.UUID, lesson_id: uuid.UUID, sequence_order: int = 0
) -> LessonCollectionItem:
    existing = await db.scalar(
        select(LessonCollectionItem).where(
            LessonCollectionItem.collection_id == collection_id,
            LessonCollectionItem.lesson_id == lesson_id,
        )
    )
    if existing is not None:
        return existing

    item = LessonCollectionItem(
        collection_id=collection_id, lesson_id=lesson_id, sequence_order=sequence_order
    )
    db.add(item)
    await db.flush()
    return item


async def submit_quality_feedback(
    db: AsyncSession,
    *,
    lesson_id: uuid.UUID,
    user_id: uuid.UUID,
    rating: int,
    comment: str | None = None,
) -> LessonQualityFeedback:
    if not 1 <= rating <= 5:
        raise ValueError("rating must be between 1 and 5")

    feedback = LessonQualityFeedback(
        lesson_id=lesson_id, user_id=user_id, rating=rating, comment=comment
    )
    db.add(feedback)
    await db.flush()
    await emit_event(
        db,
        event_type="lesson_feedback_submitted",
        payload={"lesson_id": str(lesson_id), "user_id": str(user_id), "rating": rating},
    )
    return feedback


async def list_quality_feedback(
    db: AsyncSession, *, lesson_id: uuid.UUID
) -> list[LessonQualityFeedback]:
    result = await db.scalars(
        select(LessonQualityFeedback).where(LessonQualityFeedback.lesson_id == lesson_id)
    )
    return list(result.all())
