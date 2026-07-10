import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AssignmentSession, TaskScore
from app.services import assignments as assignments_svc
from app.services.events import emit_event


async def apply_answer_scored(
    db: AsyncSession, *, session_id: uuid.UUID, task_id: uuid.UUID, correctness: float
) -> AssignmentSession | None:
    """Consumes Answers Service's 'answer_scored' event. Answers Service
    knows the answer and the correct one; it decides correctness. This
    service only knows the WEIGHTS (from assignment_tasks) and aggregates -
    it never re-derives correctness itself, per the product decision to keep
    grading logic in exactly one place.

    A teacher's manual grade (session.grade_overridden) always wins - this
    function still records the per-task score for visibility, but stops
    short of touching session.grade once overridden.
    """
    session = await db.get(AssignmentSession, session_id)
    if session is None:
        return None

    existing = await db.scalar(
        select(TaskScore).where(
            TaskScore.session_id == session_id, TaskScore.task_id == task_id
        )
    )
    if existing is not None:
        existing.correctness = correctness
    else:
        db.add(TaskScore(session_id=session_id, task_id=task_id, correctness=correctness))
    await db.flush()

    if session.grade_overridden:
        return session

    tasks = await assignments_svc.get_tasks(db, assignment_id=session.assignment_id)
    weights = {t.task_id: (t.weight if t.weight is not None else 1) for t in tasks}

    scores = (
        await db.scalars(select(TaskScore).where(TaskScore.session_id == session_id))
    ).all()

    total_weight = 0.0
    weighted_sum = 0.0
    for score in scores:
        weight = weights.get(score.task_id, 1)
        weighted_sum += float(score.correctness) * weight
        total_weight += weight

    if total_weight > 0:
        session.grade = round(weighted_sum / total_weight, 2)
        await db.flush()
        await emit_event(
            db,
            event_type="session_graded",
            payload={"session_id": str(session_id), "grade": float(session.grade)},
        )

    return session
