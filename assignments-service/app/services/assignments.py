import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, AssignmentTask, TargetType
from app.schemas import AssignmentCreate, AssignmentTaskIn, AssignmentUpdate
from app.services.events import emit_event


async def _replace_tasks(
    db: AsyncSession, *, assignment_id: uuid.UUID, tasks: list[AssignmentTaskIn]
) -> None:
    await db.execute(delete(AssignmentTask).where(AssignmentTask.assignment_id == assignment_id))
    for position, task_in in enumerate(tasks):
        db.add(
            AssignmentTask(
                assignment_id=assignment_id,
                task_id=task_in.task_id,
                position=position,
                weight=task_in.weight,
            )
        )
    await db.flush()


async def create_assignment(
    db: AsyncSession, *, teacher_id: uuid.UUID, body: AssignmentCreate
) -> Assignment:
    if body.target_type == TargetType.classroom and body.target_classroom_id is None:
        raise ValueError("target_classroom_id is required when target_type is 'classroom'")

    assignment = Assignment(
        teacher_id=teacher_id,
        lesson_id=body.lesson_id,
        title=body.title,
        deadline=body.deadline,
        time_limit_minutes=body.time_limit_minutes,
        attempts_limit=body.attempts_limit,
        show_results_immediately=body.show_results_immediately,
        target_type=body.target_type,
        target_classroom_id=body.target_classroom_id,
    )
    db.add(assignment)
    await db.flush()

    await _replace_tasks(db, assignment_id=assignment.id, tasks=body.tasks)

    await emit_event(
        db,
        event_type="assignment_created",
        payload={
            "assignment_id": str(assignment.id),
            "teacher_id": str(teacher_id),
            "lesson_id": str(body.lesson_id),
            "target_type": body.target_type.value,
            "target_classroom_id": str(body.target_classroom_id)
            if body.target_classroom_id
            else None,
        },
    )
    return assignment


async def update_assignment(
    db: AsyncSession, *, assignment: Assignment, body: AssignmentUpdate
) -> Assignment:
    changed_fields: list[str] = []
    if body.title is not None:
        assignment.title = body.title
        changed_fields.append("title")
    if body.deadline is not None:
        assignment.deadline = body.deadline
        changed_fields.append("deadline")
    if body.time_limit_minutes is not None:
        assignment.time_limit_minutes = body.time_limit_minutes
        changed_fields.append("time_limit_minutes")
    if body.attempts_limit is not None:
        assignment.attempts_limit = body.attempts_limit
        changed_fields.append("attempts_limit")
    if body.show_results_immediately is not None:
        assignment.show_results_immediately = body.show_results_immediately
        changed_fields.append("show_results_immediately")
    if body.tasks is not None:
        await _replace_tasks(db, assignment_id=assignment.id, tasks=body.tasks)
        changed_fields.append("tasks")
    await db.flush()
    if changed_fields:
        await emit_event(
            db,
            event_type="assignment_updated",
            payload={
                "assignment_id": str(assignment.id),
                "lesson_id": str(assignment.lesson_id),
                "changed_fields": changed_fields,
            },
        )
    return assignment


async def delete_assignment(db: AsyncSession, *, assignment: Assignment) -> None:
    assignment_id, teacher_id = assignment.id, assignment.teacher_id
    await db.delete(assignment)
    await db.flush()
    await emit_event(
        db,
        event_type="assignment_deleted",
        payload={"assignment_id": str(assignment_id), "teacher_id": str(teacher_id)},
    )


async def get_tasks(db: AsyncSession, *, assignment_id: uuid.UUID) -> list[AssignmentTask]:
    result = await db.scalars(
        select(AssignmentTask)
        .where(AssignmentTask.assignment_id == assignment_id)
        .order_by(AssignmentTask.position)
    )
    return list(result.all())


async def list_assignments_for_teacher(
    db: AsyncSession, *, teacher_id: uuid.UUID
) -> list[Assignment]:
    result = await db.scalars(
        select(Assignment).where(Assignment.teacher_id == teacher_id).order_by(
            Assignment.created_at.desc()
        )
    )
    return list(result.all())
