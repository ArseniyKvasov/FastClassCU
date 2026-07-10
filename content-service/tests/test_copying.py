import asyncio
import uuid

from sqlalchemy import func, select

from app.models import DerivationType, Lesson, Section, Task, TaskContent
from app.services import content as content_svc
from app.services import lessons as lessons_svc


async def _first_section(db, lesson):
    return (await db.scalars(select(Section).where(Section.lesson_id == lesson.id))).one()


async def test_copy_shares_content_and_costs_zero_quota(db_session):
    db = db_session
    teacher = uuid.uuid4()
    student = uuid.uuid4()

    original = await lessons_svc.create_lesson(db, owner_id=teacher, title="Lesson")
    section = await _first_section(db, original)
    await lessons_svc.add_task(
        db, section_id=section.id, task_type="text", payload={"content": "hi"}, created_by=teacher
    )
    clone = await lessons_svc.create_clone(db, source=original, owner_id=teacher)

    content_count_before = await db.scalar(select(func.count()).select_from(TaskContent))

    copy = await lessons_svc.create_copy(db, source=clone, owner_id=student)

    assert copy.derivation_type == DerivationType.copy
    assert copy.origin_lesson_id == clone.id

    content_count_after = await db.scalar(select(func.count()).select_from(TaskContent))
    assert content_count_after == content_count_before

    assert await content_svc.teacher_storage_bytes(db, student) == 0


async def test_second_copy_for_same_student_returns_existing_not_a_duplicate(db_session):
    db = db_session
    teacher = uuid.uuid4()
    student = uuid.uuid4()

    original = await lessons_svc.create_lesson(db, owner_id=teacher, title="Lesson")
    section = await _first_section(db, original)
    await lessons_svc.add_task(
        db, section_id=section.id, task_type="text", payload={"content": "hi"}, created_by=teacher
    )
    clone = await lessons_svc.create_clone(db, source=original, owner_id=teacher)

    copy1 = await lessons_svc.create_copy(db, source=clone, owner_id=student)
    copy2 = await lessons_svc.create_copy(db, source=clone, owner_id=student)

    assert copy1.id == copy2.id

    count = await db.scalar(
        select(func.count()).select_from(Lesson).where(
            Lesson.origin_lesson_id == clone.id,
            Lesson.owner_id == student,
            Lesson.derivation_type == DerivationType.copy,
        )
    )
    assert count == 1


async def test_concurrent_copy_requests_do_not_create_duplicates(db_session_factory):
    """The old system's one-copy-per-user rule was only an app-level
    `.filter().first()` check, which two simultaneous requests can both pass.
    Here the uniqueness is a DB constraint, so we prove it holds even when two
    separate sessions race to create the same copy at the same time."""
    teacher = uuid.uuid4()
    student = uuid.uuid4()

    async with db_session_factory() as db:
        original = await lessons_svc.create_lesson(db, owner_id=teacher, title="Lesson")
        section = await _first_section(db, original)
        await lessons_svc.add_task(
            db, section_id=section.id, task_type="text", payload={"content": "hi"}, created_by=teacher
        )
        clone = await lessons_svc.create_clone(db, source=original, owner_id=teacher)
        await db.commit()
        clone_id = clone.id

    async def attempt():
        async with db_session_factory() as db:
            src = await db.get(Lesson, clone_id)
            copy = await lessons_svc.create_copy(db, source=src, owner_id=student)
            await db.commit()
            return copy.id

    results = await asyncio.gather(attempt(), attempt())

    async with db_session_factory() as db:
        count = await db.scalar(
            select(func.count()).select_from(Lesson).where(
                Lesson.origin_lesson_id == clone_id,
                Lesson.owner_id == student,
                Lesson.derivation_type == DerivationType.copy,
            )
        )
    assert count == 1
    assert results[0] == results[1]
