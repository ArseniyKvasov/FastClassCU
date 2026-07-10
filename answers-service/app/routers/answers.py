import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.deps import CurrentUser, get_current_user
from app.models import Answer, ContextType
from app.redis_client import get_redis
from app.schemas import AnswerOut, ManualScoreUpdate, SubmitAnswerRequest
from app.services import answers as answers_svc
from app.services import events as events_svc
from app.services.context_client import get_context_teacher_id
from fastclass_shared import RateLimitExceeded, RateLimitRule, RedisRateLimiter

router = APIRouter(prefix="/answers", tags=["answers"])
_answer_submit_limiter = RedisRateLimiter(
    redis_url=settings.redis_url,
    service_name="answers-service",
)


async def _require_teacher_of(
    context_type: ContextType, context_id: uuid.UUID, user: CurrentUser
) -> None:
    teacher_id = await get_context_teacher_id(context_type, context_id, user.token)
    if teacher_id is None or teacher_id != user.user_id:
        raise HTTPException(status_code=403, detail={"code": "teacher_only"})


@router.post("", response_model=AnswerOut)
async def submit_answer(
    body: SubmitAnswerRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    r=Depends(get_redis),
):
    try:
        await _answer_submit_limiter.hit(
            RateLimitRule(
                name="submit-answer",
                limit=settings.answer_submit_rate_limit,
                window_seconds=settings.answer_submit_window_seconds,
            ),
            str(user.user_id),
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={"code": "too_many_requests", "retry_after_seconds": exc.retry_after_seconds},
        )

    try:
        answer = await answers_svc.submit_answer(
            db,
            r,
            task_id=body.task_id,
            user_id=user.user_id,
            context_type=body.context_type,
            context_id=body.context_id,
            payload=body.payload,
        )
    except answers_svc.content_client.AnswerKeyNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "task_not_found"})

    await db.commit()
    return answer


@router.get("/mine", response_model=AnswerOut | None)
async def get_my_answer(
    task_id: uuid.UUID,
    context_type: ContextType,
    context_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    answer = await answers_svc.get_answer(
        db, task_id=task_id, user_id=user.user_id, context_type=context_type, context_id=context_id
    )
    return answer


@router.get("", response_model=list[AnswerOut])
async def list_answers_for_context(
    context_type: ContextType,
    context_id: uuid.UUID,
    task_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    await _require_teacher_of(context_type, context_id, user)

    stmt = select(Answer).where(
        Answer.context_type == context_type, Answer.context_id == context_id
    )
    if task_id is not None:
        stmt = stmt.where(Answer.task_id == task_id)
    result = await db.scalars(stmt)
    return list(result.all())


async def _get_answer_or_404(answer_id: uuid.UUID, db: AsyncSession) -> Answer:
    answer = await db.get(Answer, answer_id)
    if answer is None:
        raise HTTPException(status_code=404, detail={"code": "answer_not_found"})
    return answer


@router.patch("/{answer_id}/score", response_model=AnswerOut)
async def set_manual_score(
    answer_id: uuid.UUID,
    body: ManualScoreUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    answer = await _get_answer_or_404(answer_id, db)
    await _require_teacher_of(answer.context_type, answer.context_id, user)

    answer.manual_score = body.score
    await db.flush()
    await events_svc.emit_event(
        db,
        event_type="answer_manual_score_set",
        payload={"answer_id": str(answer.id), "score": body.score},
    )

    if answer.context_type == ContextType.assignment:
        await events_svc.emit_event(
            db,
            event_type="answer_scored",
            payload={
                "session_id": str(answer.context_id),
                "task_id": str(answer.task_id),
                "correctness": body.score,
            },
        )

    await db.commit()
    return answer


@router.delete("/{answer_id}", status_code=204)
async def reset_answer(
    answer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    answer = await _get_answer_or_404(answer_id, db)
    await _require_teacher_of(answer.context_type, answer.context_id, user)

    await events_svc.emit_event(
        db,
        event_type="answer_reset",
        payload={
            "task_id": str(answer.task_id),
            "user_id": str(answer.user_id),
            "context_type": answer.context_type,
            "context_id": str(answer.context_id),
        },
    )
    await db.delete(answer)
    await db.commit()
