import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import LessonCollection, LessonCollectionItem, LessonQualityFeedback
from app.schemas import (
    CollectionCreate,
    CollectionItemCreate,
    CollectionOut,
    QualityFeedbackCreate,
    QualityFeedbackOut,
)
from app.services import collections as collections_svc

router = APIRouter(tags=["collections"])


@router.post("/collections", response_model=CollectionOut)
async def create_collection(
    body: CollectionCreate, db: AsyncSession = Depends(get_db)
) -> LessonCollection:
    collection = await collections_svc.create_collection(
        db,
        owner_id=body.owner_id,
        title=body.title,
        description=body.description,
        is_sequential=body.is_sequential,
    )
    await db.commit()
    return collection


@router.get("/collections", response_model=list[CollectionOut])
async def list_collections(
    owner_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[LessonCollection]:
    return await collections_svc.list_collections_for_owner(db, owner_id=owner_id)


@router.post("/collections/{collection_id}/items", status_code=204)
async def add_item(
    collection_id: uuid.UUID, body: CollectionItemCreate, db: AsyncSession = Depends(get_db)
) -> None:
    await collections_svc.add_lesson_to_collection(
        db,
        collection_id=collection_id,
        lesson_id=body.lesson_id,
        sequence_order=body.sequence_order,
    )
    await db.commit()


@router.post("/lessons/{lesson_id}/feedback", response_model=QualityFeedbackOut)
async def submit_feedback(
    lesson_id: uuid.UUID, body: QualityFeedbackCreate, db: AsyncSession = Depends(get_db)
) -> LessonQualityFeedback:
    feedback = await collections_svc.submit_quality_feedback(
        db,
        lesson_id=lesson_id,
        user_id=body.user_id,
        rating=body.rating,
        comment=body.comment,
    )
    await db.commit()
    return feedback


@router.get("/lessons/{lesson_id}/feedback", response_model=list[QualityFeedbackOut])
async def list_feedback(
    lesson_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[LessonQualityFeedback]:
    return await collections_svc.list_quality_feedback(db, lesson_id=lesson_id)
