import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Classroom, ClassroomSettings
from app.passwords import generate_join_password, hash_password
from app.services.events import emit_event


async def create_classroom(
    db: AsyncSession, *, teacher_id: uuid.UUID, title: str, lesson_id: uuid.UUID | None = None
) -> tuple[Classroom, str]:
    """Returns (classroom, plaintext_join_password) - the plaintext is only
    ever available at creation/rotation time, never stored or retrievable
    again (only the hash persists)."""
    classroom = Classroom(teacher_id=teacher_id, title=title, lesson_id=lesson_id)
    db.add(classroom)
    await db.flush()

    plaintext = generate_join_password(settings.join_password_min_length)
    db.add(
        ClassroomSettings(classroom_id=classroom.id, join_password_hash=hash_password(plaintext))
    )
    await db.flush()

    await emit_event(
        db,
        event_type="classroom_created",
        payload={"classroom_id": str(classroom.id), "teacher_id": str(teacher_id)},
    )
    return classroom, plaintext


async def list_classrooms_for_user(
    db: AsyncSession, *, user_id: uuid.UUID
) -> list[Classroom]:
    from app.models import Membership

    owned = (
        await db.scalars(select(Classroom).where(Classroom.teacher_id == user_id))
    ).all()
    member_of_ids = (
        await db.scalars(select(Membership.classroom_id).where(Membership.user_id == user_id))
    ).all()
    joined = (
        await db.scalars(select(Classroom).where(Classroom.id.in_(member_of_ids)))
    ).all() if member_of_ids else []
    return list(owned) + list(joined)


async def update_classroom(
    db: AsyncSession, *, classroom: Classroom, title: str | None, lesson_id
) -> Classroom:
    if title is not None:
        classroom.title = title
    if lesson_id is not None:
        classroom.lesson_id = lesson_id
    await db.flush()
    return classroom


async def delete_classroom(db: AsyncSession, *, classroom: Classroom) -> None:
    classroom_id, teacher_id = classroom.id, classroom.teacher_id
    await db.delete(classroom)
    await db.flush()
    await emit_event(
        db,
        event_type="classroom_deleted",
        payload={"classroom_id": str(classroom_id), "teacher_id": str(teacher_id)},
    )


async def get_settings(db: AsyncSession, *, classroom_id: uuid.UUID) -> ClassroomSettings | None:
    return await db.get(ClassroomSettings, classroom_id)


async def update_settings(
    db: AsyncSession,
    *,
    classroom_settings: ClassroomSettings,
    communication_enabled: bool | None,
    whiteboard_enabled: bool | None,
    copying_enabled: bool | None,
) -> ClassroomSettings:
    if communication_enabled is not None:
        classroom_settings.communication_enabled = communication_enabled
    if whiteboard_enabled is not None:
        classroom_settings.whiteboard_enabled = whiteboard_enabled
    if copying_enabled is not None:
        classroom_settings.copying_enabled = copying_enabled
    await db.flush()
    return classroom_settings
