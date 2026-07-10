import uuid

from sqlalchemy import func, select

from app.models import FileAsset, Section, Task, TaskContent
from app.services import content as content_svc
from app.services import gc as gc_svc
from app.services import lessons as lessons_svc
from app.storage import storage


async def _first_section(db, lesson):
    return (await db.scalars(select(Section).where(Section.lesson_id == lesson.id))).one()


async def test_cloning_a_file_task_does_not_duplicate_the_blob(db_session):
    db = db_session
    teacher_a = uuid.uuid4()
    teacher_b = uuid.uuid4()

    original = await lessons_svc.create_lesson(db, owner_id=teacher_a, title="Lesson")
    section = await _first_section(db, original)

    file_asset = await content_svc.create_file_asset(
        db, data=b"pdf-bytes-here", original_filename="worksheet.pdf", mime_type="application/pdf"
    )
    await lessons_svc.add_task(
        db,
        section_id=section.id,
        task_type="file",
        payload={"description": ""},
        created_by=teacher_a,
        file_id=file_asset.id,
    )

    file_count_before = await db.scalar(select(func.count()).select_from(FileAsset))
    clone = await lessons_svc.create_clone(db, source=original, owner_id=teacher_b)
    file_count_after = await db.scalar(select(func.count()).select_from(FileAsset))

    assert file_count_after == file_count_before, "clone must not duplicate the file row"

    clone_section = await _first_section(db, clone)
    clone_task = (
        await db.scalars(select(Task).where(Task.section_id == clone_section.id))
    ).one()
    clone_content = await db.get(TaskContent, clone_task.current_content_id)
    assert clone_content.file_id == file_asset.id


async def test_gc_never_deletes_a_file_still_referenced_by_a_clone(db_session):
    """The core no-leak guarantee, direction 1: deleting the lesson that
    originally owned a file must NOT delete the blob while a clone still
    points at it - that would be data loss, not just a storage optimization
    bug."""
    db = db_session
    teacher_a = uuid.uuid4()
    teacher_b = uuid.uuid4()

    original = await lessons_svc.create_lesson(db, owner_id=teacher_a, title="Lesson")
    section = await _first_section(db, original)
    file_asset = await content_svc.create_file_asset(db, data=b"shared-file-bytes", mime_type="application/pdf")
    await lessons_svc.add_task(
        db,
        section_id=section.id,
        task_type="file",
        payload={"description": ""},
        created_by=teacher_a,
        file_id=file_asset.id,
    )
    clone = await lessons_svc.create_clone(db, source=original, owner_id=teacher_b)

    assert storage.exists(file_asset.storage_key)

    # Delete the ORIGINAL lesson - the clone still references the same
    # file via its own (independent) task_content row.
    await lessons_svc.delete_lesson(db, lesson=original)

    result = await gc_svc.run_gc(db)
    assert result["reclaimed_files"] == 0, "file is still referenced by the clone"
    assert storage.exists(file_asset.storage_key)
    assert await db.get(FileAsset, file_asset.id) is not None


async def test_gc_reclaims_file_once_truly_unreferenced(db_session):
    """No-leak guarantee, direction 2: once nothing references a file at all,
    GC must actually reclaim it - otherwise blobs pile up forever, which was
    exactly the old system's silent-orphan problem."""
    db = db_session
    teacher_a = uuid.uuid4()
    teacher_b = uuid.uuid4()

    original = await lessons_svc.create_lesson(db, owner_id=teacher_a, title="Lesson")
    section = await _first_section(db, original)
    file_asset = await content_svc.create_file_asset(db, data=b"orphan-me", mime_type="application/pdf")
    await lessons_svc.add_task(
        db,
        section_id=section.id,
        task_type="file",
        payload={"description": ""},
        created_by=teacher_a,
        file_id=file_asset.id,
    )
    clone = await lessons_svc.create_clone(db, source=original, owner_id=teacher_b)

    storage_key = file_asset.storage_key
    file_id = file_asset.id

    # Delete BOTH the original and the clone - now nothing references the file.
    await lessons_svc.delete_lesson(db, lesson=original)
    await lessons_svc.delete_lesson(db, lesson=clone)

    # A GC pass beforehand shouldn't have anything to do while rows still
    # existed; now it should reclaim everything.
    result = await gc_svc.run_gc(db)

    assert result["reclaimed_files"] == 1
    assert not storage.exists(storage_key)
    assert await db.get(FileAsset, file_id) is None


async def test_gc_credits_freed_bytes_back_to_quota(db_session):
    db = db_session
    teacher = uuid.uuid4()

    original = await lessons_svc.create_lesson(db, owner_id=teacher, title="Lesson")
    section = await _first_section(db, original)
    await lessons_svc.add_task(
        db,
        section_id=section.id,
        task_type="text",
        payload={"content": "some real content that takes up space"},
        created_by=teacher,
    )

    bytes_before_delete = await content_svc.teacher_storage_bytes(db, teacher)
    assert bytes_before_delete > 0

    await lessons_svc.delete_lesson(db, lesson=original)
    await gc_svc.run_gc(db)

    bytes_after_gc = await content_svc.teacher_storage_bytes(db, teacher)
    assert bytes_after_gc == 0
