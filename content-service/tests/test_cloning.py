import uuid

from sqlalchemy import func, select

from app.models import DerivationType, Lesson, Section, Task, TaskContent, TeacherQuota
from app.services import content as content_svc
from app.services import lessons as lessons_svc


async def _lesson_task(db, lesson):
    section = (
        await db.scalars(select(Section).where(Section.lesson_id == lesson.id))
    ).one()
    task = (await db.scalars(select(Task).where(Task.section_id == section.id))).one()
    return section, task


async def test_clone_creates_no_new_content_and_costs_zero_quota(db_session):
    db = db_session
    teacher_a = uuid.uuid4()
    teacher_b = uuid.uuid4()

    original = await lessons_svc.create_lesson(db, owner_id=teacher_a, title="Present Simple")
    _, section = None, None
    section = (
        await db.scalars(select(Section).where(Section.lesson_id == original.id))
    ).one()
    await lessons_svc.add_task(
        db,
        section_id=section.id,
        task_type="text",
        payload={"content": "hello"},
        created_by=teacher_a,
    )

    content_count_before = (await db.scalar(select(func.count()).select_from(TaskContent)))

    clone = await lessons_svc.create_clone(db, source=original, owner_id=teacher_b)

    assert clone.derivation_type == DerivationType.clone
    assert clone.origin_lesson_id == original.id
    assert clone.owner_id == teacher_b

    content_count_after = (await db.scalar(select(func.count()).select_from(TaskContent)))
    assert content_count_after == content_count_before, "clone must not create new content rows"

    # teacher_b's quota untouched by cloning someone else's lesson
    b_bytes = await content_svc.teacher_storage_bytes(db, teacher_b)
    assert b_bytes == 0

    _, orig_task = await _lesson_task(db, original)
    _, clone_task = await _lesson_task(db, clone)
    assert clone_task.current_content_id == orig_task.current_content_id
    assert clone_task.origin_task_id == orig_task.id


async def test_editing_original_does_not_touch_existing_clone(db_session):
    db = db_session
    teacher_a = uuid.uuid4()
    teacher_b = uuid.uuid4()

    original = await lessons_svc.create_lesson(db, owner_id=teacher_a, title="Lesson")
    section = (
        await db.scalars(select(Section).where(Section.lesson_id == original.id))
    ).one()
    await lessons_svc.add_task(
        db, section_id=section.id, task_type="text", payload={"content": "v1"}, created_by=teacher_a
    )
    clone = await lessons_svc.create_clone(db, source=original, owner_id=teacher_b)

    _, orig_task_before = await _lesson_task(db, original)
    _, clone_task_before = await _lesson_task(db, clone)
    # Capture plain values, not ORM object references - the same session's
    # identity map would hand back the SAME Python object on the next query,
    # so comparing objects after mutating one of them proves nothing.
    orig_content_id_before = orig_task_before.current_content_id
    clone_content_id_before = clone_task_before.current_content_id
    assert clone_content_id_before == orig_content_id_before

    # Edit the original - do NOT sync.
    _, orig_task = await _lesson_task(db, original)
    await lessons_svc.update_task(
        db, task=orig_task, payload={"content": "v2 - edited"}, edited_by=teacher_a
    )

    _, orig_task_after = await _lesson_task(db, original)
    _, clone_task_after = await _lesson_task(db, clone)

    assert orig_task_after.current_content_id != orig_content_id_before
    # The clone must be completely unaffected until an explicit sync.
    assert clone_task_after.current_content_id == clone_content_id_before

    orig_content = await db.get(TaskContent, orig_task_after.current_content_id)
    clone_content = await db.get(TaskContent, clone_task_after.current_content_id)
    assert orig_content.payload["content"] == "v2 - edited"
    assert clone_content.payload["content"] == "v1"


async def test_sync_pulls_original_into_clone_and_overrides_local_edit(db_session):
    db = db_session
    teacher_a = uuid.uuid4()
    teacher_b = uuid.uuid4()

    original = await lessons_svc.create_lesson(db, owner_id=teacher_a, title="Lesson")
    section = (
        await db.scalars(select(Section).where(Section.lesson_id == original.id))
    ).one()
    await lessons_svc.add_task(
        db, section_id=section.id, task_type="text", payload={"content": "v1"}, created_by=teacher_a
    )
    clone = await lessons_svc.create_clone(db, source=original, owner_id=teacher_b)

    # Clone owner edits their copy independently (diverges).
    _, clone_task = await _lesson_task(db, clone)
    await lessons_svc.update_task(
        db, task=clone_task, payload={"content": "student's own edit"}, edited_by=teacher_b
    )

    # Teacher edits the original.
    _, orig_task = await _lesson_task(db, original)
    await lessons_svc.update_task(
        db, task=orig_task, payload={"content": "official update"}, edited_by=teacher_a
    )

    report = await lessons_svc.sync_derived_lesson(db, derived=clone)

    _, clone_task_after = await _lesson_task(db, clone)
    clone_content = await db.get(TaskContent, clone_task_after.current_content_id)
    # Product decision: origin always wins, even over the clone owner's edit.
    assert clone_content.payload["content"] == "official update"
    assert clone_task.id in report["overwritten_edited"]


async def test_sync_cascades_to_copies_of_the_clone(db_session):
    db = db_session
    teacher_a = uuid.uuid4()
    teacher_b = uuid.uuid4()
    student_c = uuid.uuid4()

    original = await lessons_svc.create_lesson(db, owner_id=teacher_a, title="Lesson")
    section = (
        await db.scalars(select(Section).where(Section.lesson_id == original.id))
    ).one()
    await lessons_svc.add_task(
        db, section_id=section.id, task_type="text", payload={"content": "v1"}, created_by=teacher_a
    )
    clone = await lessons_svc.create_clone(db, source=original, owner_id=teacher_b)
    copy = await lessons_svc.create_copy(db, source=clone, owner_id=student_c)

    _, orig_task = await _lesson_task(db, original)
    await lessons_svc.update_task(
        db, task=orig_task, payload={"content": "v2"}, edited_by=teacher_a
    )

    # Teacher syncs only the clone - this must cascade down to the student's copy.
    await lessons_svc.sync_derived_lesson(db, derived=clone)

    _, copy_task = await _lesson_task(db, copy)
    copy_content = await db.get(TaskContent, copy_task.current_content_id)
    assert copy_content.payload["content"] == "v2"
