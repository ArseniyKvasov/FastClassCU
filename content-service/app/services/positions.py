from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Section, Task


async def next_section_position(db: AsyncSession, lesson_id) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(Section.position), -1)).where(
            Section.lesson_id == lesson_id
        )
    )
    return result.scalar_one() + 1


async def next_task_position(db: AsyncSession, section_id) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(Task.position), -1)).where(
            Task.section_id == section_id
        )
    )
    return result.scalar_one() + 1
