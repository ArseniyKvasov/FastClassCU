import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.deps import CurrentUser, get_assignment_or_404, get_current_user
from app.models import Assignment, AssignmentSession, TargetType
from app.redis_client import get_redis
from app.schemas import SessionCommentUpdate, SessionGradeOverride, SessionOut, SessionStatusUpdate
from app.services import sessions as sessions_svc
from app.services.classroom_client import is_classroom_member
from app.ws.manager import publish
from fastclass_shared import RateLimitExceeded, RateLimitRule, RedisRateLimiter

router = APIRouter(tags=["sessions"])
_session_start_limiter = RedisRateLimiter(
    redis_url=settings.redis_url,
    service_name="assignments-service",
)


async def _get_session_or_404(session_id: uuid.UUID, db: AsyncSession) -> AssignmentSession:
    session = await db.get(AssignmentSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail={"code": "session_not_found"})
    return session


async def _require_session_access(
    session: AssignmentSession, assignment: Assignment, user: CurrentUser
) -> None:
    if user.user_id == session.student_id:
        return
    if user.user_id == assignment.teacher_id:
        return
    raise HTTPException(status_code=403, detail={"code": "not_your_session"})


async def _to_out(assignment: Assignment, session: AssignmentSession) -> dict:
    return {
        **SessionOut.model_validate(session).model_dump(exclude={"time_left_seconds"}),
        "time_left_seconds": sessions_svc.compute_time_left_seconds(assignment, session),
    }


@router.post("/assignments/{assignment_id}/sessions", response_model=SessionOut)
async def start_session(
    assignment: Assignment = Depends(get_assignment_or_404),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    try:
        await _session_start_limiter.hit(
            RateLimitRule(
                name="start-session",
                limit=settings.session_start_rate_limit,
                window_seconds=settings.session_start_window_seconds,
            ),
            str(user.user_id),
            str(assignment.id),
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={"code": "too_many_requests", "retry_after_seconds": exc.retry_after_seconds},
        )

    if assignment.target_type == TargetType.classroom:
        allowed = await is_classroom_member(assignment.target_classroom_id, user.token)
        if not allowed:
            raise HTTPException(status_code=403, detail={"code": "not_a_classroom_member"})

    try:
        session = await sessions_svc.start_session(
            db, assignment=assignment, student_id=user.user_id
        )
    except sessions_svc.AttemptsExceededError:
        raise HTTPException(status_code=409, detail={"code": "attempts_exceeded"})
    except sessions_svc.AssignmentExpiredError:
        raise HTTPException(status_code=410, detail={"code": "assignment_expired"})

    await db.commit()
    return await _to_out(assignment, session)


@router.get("/assignments/{assignment_id}/sessions/mine", response_model=list[SessionOut])
async def list_my_sessions(
    assignment: Assignment = Depends(get_assignment_or_404),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    items = await sessions_svc.list_sessions_for_student(
        db, assignment_id=assignment.id, student_id=user.user_id
    )
    return [await _to_out(assignment, s) for s in items]


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    session = await _get_session_or_404(session_id, db)
    assignment = await db.get(Assignment, session.assignment_id)
    await _require_session_access(session, assignment, user)

    await sessions_svc.maybe_expire(db, assignment=assignment, session=session)
    await db.commit()
    return await _to_out(assignment, session)


@router.post("/sessions/{session_id}/submit", response_model=SessionOut)
async def submit_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    r=Depends(get_redis),
):
    session = await _get_session_or_404(session_id, db)
    assignment = await db.get(Assignment, session.assignment_id)
    if user.user_id != session.student_id:
        raise HTTPException(status_code=403, detail={"code": "not_your_session"})

    if await sessions_svc.maybe_expire(db, assignment=assignment, session=session):
        await db.commit()
        raise HTTPException(status_code=410, detail={"code": "session_expired"})

    session = await sessions_svc.submit_session(db, session=session)
    await db.commit()

    await publish(
        r,
        assignment_id=assignment.id,
        message={
            "type": "session_submitted",
            "session_id": str(session.id),
            "student_id": str(session.student_id),
        },
    )
    return await _to_out(assignment, session)


async def _require_teacher_of_session(
    session_id: uuid.UUID, db: AsyncSession, user: CurrentUser
) -> tuple[AssignmentSession, Assignment]:
    session = await _get_session_or_404(session_id, db)
    assignment = await db.get(Assignment, session.assignment_id)
    if user.user_id != assignment.teacher_id:
        raise HTTPException(status_code=403, detail={"code": "teacher_only"})
    return session, assignment


@router.get("/assignments/{assignment_id}/sessions", response_model=list[SessionOut])
async def list_all_sessions(
    assignment: Assignment = Depends(get_assignment_or_404),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    if user.user_id != assignment.teacher_id:
        raise HTTPException(status_code=403, detail={"code": "teacher_only"})
    items = await sessions_svc.list_sessions_for_assignment(db, assignment_id=assignment.id)
    return [await _to_out(assignment, s) for s in items]


@router.patch("/sessions/{session_id}/status", response_model=SessionOut)
async def set_session_status(
    session_id: uuid.UUID,
    body: SessionStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    r=Depends(get_redis),
):
    session, assignment = await _require_teacher_of_session(session_id, db, user)
    session = await sessions_svc.set_status(db, session=session, status=body.status)
    await db.commit()
    await publish(
        r,
        assignment_id=assignment.id,
        message={
            "type": "session_status_changed",
            "session_id": str(session.id),
            "status": session.status,
        },
    )
    return await _to_out(assignment, session)


@router.patch("/sessions/{session_id}/comment", response_model=SessionOut)
async def set_session_comment(
    session_id: uuid.UUID,
    body: SessionCommentUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    session, assignment = await _require_teacher_of_session(session_id, db, user)
    session = await sessions_svc.set_comment(db, session=session, comment=body.comment)
    await db.commit()
    return await _to_out(assignment, session)


@router.patch("/sessions/{session_id}/grade", response_model=SessionOut)
async def override_session_grade(
    session_id: uuid.UUID,
    body: SessionGradeOverride,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    r=Depends(get_redis),
):
    session, assignment = await _require_teacher_of_session(session_id, db, user)
    session = await sessions_svc.override_grade(db, session=session, grade=body.grade)
    await db.commit()
    await publish(
        r,
        assignment_id=assignment.id,
        message={
            "type": "session_grade_changed",
            "session_id": str(session.id),
            "grade": float(session.grade),
        },
    )
    return await _to_out(assignment, session)
