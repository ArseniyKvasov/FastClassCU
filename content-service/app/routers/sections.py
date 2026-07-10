import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Lesson, Section
from app.schemas import SectionCreate, SectionOut
from app.services.positions import next_section_position

router = APIRouter(tags=["sections"])


@router.post("/lessons/{lesson_id}/sections", response_model=SectionOut)
async def create_section(
    lesson_id: uuid.UUID, body: SectionCreate, db: AsyncSession = Depends(get_db)
) -> Section:
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail={"code": "lesson_not_found"})

    section = Section(
        lesson_id=lesson_id, title=body.title, position=await next_section_position(db, lesson_id)
    )
    db.add(section)
    await db.commit()
    return section


@router.get("/lessons/{lesson_id}/sections", response_model=list[SectionOut])
async def list_sections(lesson_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[Section]:
    """Pure read - unlike the old lesson_sections view, this never creates a
    default section as a side effect. That happens once, explicitly, in
    create_lesson."""
    result = await db.scalars(
        select(Section).where(Section.lesson_id == lesson_id).order_by(Section.position)
    )
    return list(result.all())
