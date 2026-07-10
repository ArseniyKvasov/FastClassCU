import uuid

from app.services import events as events_svc
from app.services import lessons as lessons_svc


async def _first_section(db, lesson):
    from sqlalchemy import select

    from app.models import Section

    return (await db.scalars(select(Section).where(Section.lesson_id == lesson.id))).one()


async def test_task_update_emits_event_in_same_transaction(db_session):
    db = db_session
    teacher = uuid.uuid4()

    lesson = await lessons_svc.create_lesson(db, owner_id=teacher, title="Lesson")
    section = await _first_section(db, lesson)
    task = await lessons_svc.add_task(
        db, section_id=section.id, task_type="text", payload={"content": "v1"}, created_by=teacher
    )

    before = await events_svc.list_unpublished_events(db)
    await lessons_svc.update_task(db, task=task, payload={"content": "v2"}, edited_by=teacher)
    after = await events_svc.list_unpublished_events(db)

    assert len(after) == len(before) + 1
    new_event = after[-1]
    assert new_event.event_type == "task_updated"
    assert new_event.payload["task_id"] == str(task.id)
    assert new_event.published_at is None


async def test_clone_copy_delete_all_emit_events(db_session):
    db = db_session
    teacher = uuid.uuid4()
    student = uuid.uuid4()

    lesson = await lessons_svc.create_lesson(db, owner_id=teacher, title="Lesson")
    section = await _first_section(db, lesson)
    await lessons_svc.add_task(
        db, section_id=section.id, task_type="text", payload={"content": "v1"}, created_by=teacher
    )
    clone = await lessons_svc.create_clone(db, source=lesson, owner_id=teacher)
    await lessons_svc.create_copy(db, source=clone, owner_id=student)
    await lessons_svc.delete_lesson(db, lesson=clone)

    events = await events_svc.list_unpublished_events(db)
    event_types = [e.event_type for e in events]
    assert "lesson_cloned" in event_types
    assert "lesson_copied" in event_types
    assert "lesson_deleted" in event_types


async def test_mark_published_excludes_from_next_poll(db_session):
    db = db_session
    teacher = uuid.uuid4()

    lesson = await lessons_svc.create_lesson(db, owner_id=teacher, title="Lesson")
    section = await _first_section(db, lesson)
    await lessons_svc.add_task(
        db, section_id=section.id, task_type="text", payload={"content": "v1"}, created_by=teacher
    )

    pending = await events_svc.list_unpublished_events(db)
    assert len(pending) >= 1

    await events_svc.mark_published(db, [e.id for e in pending])

    still_pending = await events_svc.list_unpublished_events(db)
    assert still_pending == []
