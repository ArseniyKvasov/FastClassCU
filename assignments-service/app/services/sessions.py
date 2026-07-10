import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, AssignmentSession, SessionStatus
from app.services.events import emit_event


class AttemptsExceededError(Exception):
    pass


class AssignmentExpiredError(Exception):
    pass


def compute_time_left_seconds(assignment: Assignment, session: AssignmentSession) -> int | None:
    """None means unlimited (no time_limit and no deadline)."""
    if session.status != SessionStatus.active:
        return 0

    now = datetime.now(timezone.utc)
    candidates: list[float] = []

    if assignment.time_limit_minutes:
        elapsed = (now - session.started_at).total_seconds()
        candidates.append(assignment.time_limit_minutes * 60 - elapsed)

    if assignment.deadline:
        candidates.append((assignment.deadline - now).total_seconds())

    if not candidates:
        return None
    return max(0, int(min(candidates)))


def _is_expired(assignment: Assignment, session: AssignmentSession) -> bool:
    if session.status != SessionStatus.active:
        return False
    time_left = compute_time_left_seconds(assignment, session)
    return time_left is not None and time_left <= 0


async def maybe_expire(
    db: AsyncSession, *, assignment: Assignment, session: AssignmentSession
) -> bool:
    """Eager expiry check for whoever happens to be looking right now - the
    background sweeper (services/sweeper.py) is the AUTHORITATIVE mechanism
    that guarantees this happens even if nobody ever looks again, but there's
    no reason to make the one person actively viewing it wait for the next
    sweep when we can just tell the truth immediately."""
    if not _is_expired(assignment, session):
        return False

    session.status = SessionStatus.expired
    session.submitted_at = datetime.now(timezone.utc)
    await db.flush()
    await emit_event(
        db,
        event_type="session_expired",
        payload={"session_id": str(session.id), "assignment_id": str(assignment.id)},
    )
    return True


async def start_session(
    db: AsyncSession, *, assignment: Assignment, student_id: uuid.UUID
) -> AssignmentSession:
    if assignment.deadline and datetime.now(timezone.utc) > assignment.deadline:
        raise AssignmentExpiredError()

    existing_count = await db.scalar(
        select(func.count()).select_from(AssignmentSession).where(
            AssignmentSession.assignment_id == assignment.id,
            AssignmentSession.student_id == student_id,
        )
    )
    if existing_count >= assignment.attempts_limit:
        raise AttemptsExceededError()

    session = AssignmentSession(
        assignment_id=assignment.id,
        student_id=student_id,
        attempt_number=existing_count + 1,
    )
    db.add(session)
    await db.flush()

    await emit_event(
        db,
        event_type="session_started",
        payload={
            "session_id": str(session.id),
            "assignment_id": str(assignment.id),
            "student_id": str(student_id),
        },
    )
    return session


async def submit_session(db: AsyncSession, *, session: AssignmentSession) -> AssignmentSession:
    if session.status != SessionStatus.active:
        return session
    session.status = SessionStatus.submitted
    session.submitted_at = datetime.now(timezone.utc)
    await db.flush()
    await emit_event(
        db,
        event_type="session_submitted",
        payload={"session_id": str(session.id), "assignment_id": str(session.assignment_id)},
    )
    return session


async def set_status(
    db: AsyncSession, *, session: AssignmentSession, status: SessionStatus
) -> AssignmentSession:
    session.status = status
    await db.flush()
    await emit_event(
        db,
        event_type="session_status_changed",
        payload={"session_id": str(session.id), "status": status.value},
    )
    return session


async def set_comment(
    db: AsyncSession, *, session: AssignmentSession, comment: str
) -> AssignmentSession:
    session.teacher_comment = comment
    session.teacher_comment_updated_at = datetime.now(timezone.utc)
    await db.flush()
    return session


async def override_grade(
    db: AsyncSession, *, session: AssignmentSession, grade: float
) -> AssignmentSession:
    """Manual teacher override - always wins over the auto-aggregated grade
    from Answers Service's answer_scored events (the consumer in
    services/grading.py only ever sets grade for sessions that haven't been
    manually overridden - see its own docstring)."""
    session.grade = grade
    session.grade_overridden = True
    await db.flush()
    await emit_event(
        db,
        event_type="session_grade_overridden",
        payload={"session_id": str(session.id), "grade": grade},
    )
    return session


async def list_sessions_for_student(
    db: AsyncSession, *, assignment_id: uuid.UUID, student_id: uuid.UUID
) -> list[AssignmentSession]:
    result = await db.scalars(
        select(AssignmentSession).where(
            AssignmentSession.assignment_id == assignment_id,
            AssignmentSession.student_id == student_id,
        ).order_by(AssignmentSession.attempt_number)
    )
    return list(result.all())


async def list_sessions_for_assignment(
    db: AsyncSession, *, assignment_id: uuid.UUID
) -> list[AssignmentSession]:
    result = await db.scalars(
        select(AssignmentSession)
        .where(AssignmentSession.assignment_id == assignment_id)
        .order_by(AssignmentSession.started_at.desc())
    )
    return list(result.all())
