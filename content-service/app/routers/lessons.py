import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Lesson, Section, Task
from app.schemas import DeriveLessonRequest, LessonCreate, LessonListItemOut, LessonOut, SyncReport
from app.services import lessons as lessons_svc

router = APIRouter(prefix="/lessons", tags=["lessons"])


async def _get_lesson_or_404(db: AsyncSession, lesson_id: uuid.UUID) -> Lesson:
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail={"code": "lesson_not_found"})
    return lesson


@router.post("", response_model=LessonOut)
async def create_lesson(body: LessonCreate, db: AsyncSession = Depends(get_db)) -> Lesson:
    lesson = await lessons_svc.create_lesson(
        db, owner_id=body.owner_id, title=body.title, description=body.description
    )
    await db.commit()
    return lesson


@router.get("", response_model=list[LessonListItemOut])
async def list_lessons(owner_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Every lesson row this owner has - originals, clones they've added, and
    copies they've made - regardless of derivation_type. A clone is already
    "theirs" the moment they clone it (own row, own id); the distinction only
    matters when something downstream needs an immutable snapshot, which is
    what /copy is for. Includes a task_count per lesson (one query, not N+1)
    so callers can show it or gate on "has any lessons with content" without
    a second round trip per lesson."""
    lessons = (
        await db.scalars(
            select(Lesson).where(Lesson.owner_id == owner_id).order_by(Lesson.updated_at.desc())
        )
    ).all()

    counts_result = await db.execute(
        select(Section.lesson_id, func.count(Task.id))
        .join(Task, Task.section_id == Section.id)
        .where(Section.lesson_id.in_([lesson.id for lesson in lessons]))
        .group_by(Section.lesson_id)
    )
    counts = dict(counts_result.all())

    return [
        {**LessonOut.model_validate(lesson).model_dump(), "task_count": counts.get(lesson.id, 0)}
        for lesson in lessons
    ]


@router.get("/{lesson_id}", response_model=LessonOut)
async def get_lesson(lesson_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Lesson:
    return await _get_lesson_or_404(db, lesson_id)


@router.post("/{lesson_id}/clone", response_model=LessonOut)
async def clone_lesson(
    lesson_id: uuid.UUID, body: DeriveLessonRequest, db: AsyncSession = Depends(get_db)
) -> Lesson:
    source = await _get_lesson_or_404(db, lesson_id)
    clone = await lessons_svc.create_clone(db, source=source, owner_id=body.owner_id)
    await db.commit()
    return clone


@router.post("/{lesson_id}/copy", response_model=LessonOut)
async def copy_lesson(
    lesson_id: uuid.UUID, body: DeriveLessonRequest, db: AsyncSession = Depends(get_db)
) -> Lesson:
    source = await _get_lesson_or_404(db, lesson_id)
    copy = await lessons_svc.create_copy(db, source=source, owner_id=body.owner_id)
    await db.commit()
    return copy


@router.post("/{lesson_id}/sync", response_model=SyncReport)
async def sync_lesson(lesson_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    derived = await _get_lesson_or_404(db, lesson_id)
    if derived.origin_lesson_id is None:
        raise HTTPException(status_code=400, detail={"code": "not_a_derived_lesson"})
    report = await lessons_svc.sync_derived_lesson(db, derived=derived)
    await db.commit()
    return report


@router.delete("/{lesson_id}", status_code=204)
async def delete_lesson(lesson_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    lesson = await _get_lesson_or_404(db, lesson_id)
    await lessons_svc.delete_lesson(db, lesson=lesson)
    await db.commit()
