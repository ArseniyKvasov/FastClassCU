"""Copy-on-write lesson engine.

Mental model (two layers):
  * Structure (Lesson / Section / Task rows) is cheap and always duplicated
    when deriving - each derived lesson gets its own thin rows.
  * Content (TaskContent / FileAsset rows) is immutable and SHARED by pointer.
    Deriving points at the source's existing content rows; editing forks a new
    content row and repoints only the one task edited.

So a clone/copy costs a handful of tiny structural rows and ZERO content/file
duplication. Content only ever multiplies when someone actually edits.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DerivationType, Lesson, Section, Task
from app.services import content as content_svc
from app.services.events import emit_event
from app.services.positions import next_section_position, next_task_position


async def create_lesson(
    db: AsyncSession, *, owner_id: uuid.UUID, title: str, description: str | None = None
) -> Lesson:
    lesson = Lesson(
        owner_id=owner_id,
        title=title,
        description=description,
        derivation_type=DerivationType.original,
    )
    db.add(lesson)
    await db.flush()
    # Create the default section in the same transaction - not lazily on a GET
    # (the old code did the latter, making a read endpoint mutate data).
    db.add(Section(lesson_id=lesson.id, title="", position=0))
    await db.flush()
    await emit_event(
        db,
        event_type="lesson_created",
        payload={"lesson_id": str(lesson.id), "owner_id": str(owner_id)},
    )
    return lesson


async def add_task(
    db: AsyncSession,
    *,
    section_id: uuid.UUID,
    task_type: str,
    payload: dict,
    created_by: uuid.UUID,
    file_id: uuid.UUID | None = None,
) -> Task:
    content = await content_svc.get_or_create_content(
        db, task_type=task_type, payload=payload, created_by=created_by, file_id=file_id
    )
    task = Task(
        section_id=section_id,
        task_type=task_type,
        current_content_id=content.id,
        synced_from_content_id=content.id,
        position=await next_task_position(db, section_id),
    )
    db.add(task)
    await db.flush()
    await emit_event(
        db,
        event_type="task_created",
        payload={"task_id": str(task.id), "section_id": str(section_id)},
    )
    return task


async def update_task(
    db: AsyncSession,
    *,
    task: Task,
    payload: dict,
    edited_by: uuid.UUID,
    file_id: uuid.UUID | None = None,
) -> Task:
    """Never mutates the existing content row. Creates/reuses a content row for
    the new payload and repoints ONLY this task. Any other task (original,
    sibling clones/copies) still pointing at the old content is untouched -
    this is what keeps a clone unaffected when the original is edited."""
    content = await content_svc.get_or_create_content(
        db, task_type=task.task_type, payload=payload, created_by=edited_by, file_id=file_id
    )
    task.current_content_id = content.id
    # synced_from_content_id intentionally NOT updated: it still records what
    # this task last inherited, so we can tell the owner was edited before a
    # sync overwrites it.
    await db.flush()

    # Classroom/Assignments care that answers keyed to this task may need
    # recalculating - they subscribe to this instead of Content Service
    # importing their models directly.
    await emit_event(
        db,
        event_type="task_updated",
        payload={"task_id": str(task.id), "content_id": str(content.id)},
    )
    return task


async def _clone_structure(
    db: AsyncSession,
    *,
    source: Lesson,
    owner_id: uuid.UUID,
    derivation_type: DerivationType,
) -> Lesson:
    """Shared engine for both clone and copy: duplicate structural rows,
    point tasks at the SAME content rows as the source. No content/file rows
    created, no quota touched."""
    derived = Lesson(
        owner_id=owner_id,
        origin_lesson_id=source.id,
        derivation_type=derivation_type,
        title=source.title,
        description=source.description,
        is_public=False,
    )
    db.add(derived)
    await db.flush()

    src_sections = (
        await db.scalars(
            select(Section).where(Section.lesson_id == source.id).order_by(Section.position)
        )
    ).all()

    for src_section in src_sections:
        new_section = Section(
            lesson_id=derived.id,
            origin_section_id=src_section.id,
            title=src_section.title,
            position=src_section.position,
        )
        db.add(new_section)
        await db.flush()

        src_tasks = (
            await db.scalars(
                select(Task)
                .where(Task.section_id == src_section.id)
                .order_by(Task.position)
            )
        ).all()
        for src_task in src_tasks:
            db.add(
                Task(
                    section_id=new_section.id,
                    origin_task_id=src_task.id,
                    task_type=src_task.task_type,
                    current_content_id=src_task.current_content_id,  # SHARED
                    synced_from_content_id=src_task.current_content_id,
                    position=src_task.position,
                )
            )
        await db.flush()

    return derived


async def create_clone(db: AsyncSession, *, source: Lesson, owner_id: uuid.UUID) -> Lesson:
    clone = await _clone_structure(
        db, source=source, owner_id=owner_id, derivation_type=DerivationType.clone
    )
    await emit_event(
        db,
        event_type="lesson_cloned",
        payload={"source_lesson_id": str(source.id), "clone_lesson_id": str(clone.id)},
    )
    return clone


async def create_copy(db: AsyncSession, *, source: Lesson, owner_id: uuid.UUID) -> Lesson:
    """One copy per (source, owner) - enforced by a partial unique index, not
    an app-level check-then-create (which races). We attempt the insert
    inside a savepoint; if the DB rejects it as a duplicate, roll back just
    that savepoint and return the copy that already exists instead of
    creating a second one."""
    try:
        async with db.begin_nested():
            copy = await _clone_structure(
                db, source=source, owner_id=owner_id, derivation_type=DerivationType.copy
            )
            await emit_event(
                db,
                event_type="lesson_copied",
                payload={"source_lesson_id": str(source.id), "copy_lesson_id": str(copy.id)},
            )
            return copy
    except IntegrityError:
        existing = await db.scalar(
            select(Lesson).where(
                Lesson.origin_lesson_id == source.id,
                Lesson.owner_id == owner_id,
                Lesson.derivation_type == DerivationType.copy,
            )
        )
        if existing is None:
            raise
        return existing


async def sync_derived_lesson(db: AsyncSession, *, derived: Lesson) -> dict:
    """Force-pull content from the derived lesson's immediate parent, then
    cascade to all copies of this lesson.

    Product decisions baked in:
      * Parent always wins - overwrite even locally-edited tasks (but report
        which ones so the owner can be notified).
      * Cascade: syncing a clone immediately re-syncs every copy made from it,
        so a teacher's one action reaches all students' copies.
    """
    if derived.origin_lesson_id is None:
        raise ValueError("Lesson has no origin to sync from")

    parent = await db.get(Lesson, derived.origin_lesson_id)
    overwritten_edited: list[uuid.UUID] = []

    # Map parent tasks by their own id (the derived task's origin_task_id
    # points here).
    parent_tasks = {
        t.id: t
        for t in (
            await db.scalars(
                select(Task)
                .join(Section, Task.section_id == Section.id)
                .where(Section.lesson_id == parent.id)
            )
        ).all()
    }

    derived_tasks = (
        await db.scalars(
            select(Task)
            .join(Section, Task.section_id == Section.id)
            .where(Section.lesson_id == derived.id)
        )
    ).all()

    for dtask in derived_tasks:
        ptask = parent_tasks.get(dtask.origin_task_id)
        if ptask is None:
            # Task removed from parent -> remove from derived (parent wins).
            await db.delete(dtask)
            continue
        if dtask.current_content_id != ptask.current_content_id:
            # Was it the owner's own edit we're about to overwrite?
            if dtask.current_content_id != dtask.synced_from_content_id:
                overwritten_edited.append(dtask.id)
            dtask.current_content_id = ptask.current_content_id
            dtask.synced_from_content_id = ptask.current_content_id

    await db.flush()

    # Cascade to copies of this lesson.
    child_copies = (
        await db.scalars(
            select(Lesson).where(
                Lesson.origin_lesson_id == derived.id,
                Lesson.derivation_type == DerivationType.copy,
            )
        )
    ).all()
    for copy in child_copies:
        child_report = await sync_derived_lesson(db, derived=copy)
        overwritten_edited.extend(child_report["overwritten_edited"])

    await emit_event(
        db,
        event_type="lesson_synced",
        payload={
            "lesson_id": str(derived.id),
            "overwritten_task_ids": [str(t) for t in overwritten_edited],
        },
    )
    return {"synced_lesson_id": derived.id, "overwritten_edited": overwritten_edited}


async def delete_lesson(db: AsyncSession, *, lesson: Lesson) -> None:
    """Deletes only structural rows (sections/tasks cascade via FK). Content
    and files are never deleted here - the GC reaper reclaims them only once
    nothing references them anymore."""
    lesson_id, owner_id = lesson.id, lesson.owner_id
    await db.delete(lesson)
    await db.flush()
    await emit_event(
        db,
        event_type="lesson_deleted",
        payload={"lesson_id": str(lesson_id), "owner_id": str(owner_id)},
    )
