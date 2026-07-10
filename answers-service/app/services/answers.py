import uuid
from datetime import datetime, timezone

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import checkers
from app.models import Answer, ContextType
from app.services import content_client
from app.services.events import emit_event


async def get_answer(
    db: AsyncSession,
    *,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
    context_type: ContextType,
    context_id: uuid.UUID,
) -> Answer | None:
    return await db.scalar(
        select(Answer).where(
            Answer.task_id == task_id,
            Answer.user_id == user_id,
            Answer.context_type == context_type,
            Answer.context_id == context_id,
        )
    )


def _correctness_percentage(correct: int, wrong: int) -> float | None:
    denominator = correct + wrong
    if denominator == 0:
        return None
    return round(100 * correct / denominator, 2)


async def submit_answer(
    db: AsyncSession,
    r: redis.Redis,
    *,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
    context_type: ContextType,
    context_id: uuid.UUID,
    payload: dict,
    file_id: uuid.UUID | None = None,
) -> Answer:
    """One write path for both a live-classroom answer and a homework answer
    - the old system had two separate view functions duplicating the same
    upsert-then-score logic. Here context_type/context_id is just data, not
    a fork in the code path."""
    key_response = await content_client.get_answer_key(r, task_id=task_id)
    task_type = key_response["task_type"]
    content_id = uuid.UUID(key_response["content_id"])
    answer_key = key_response["answer_key"]

    answer = await get_answer(
        db, task_id=task_id, user_id=user_id, context_type=context_type, context_id=context_id
    )
    is_new = answer is None
    if answer is None:
        answer = Answer(
            task_id=task_id,
            user_id=user_id,
            context_type=context_type,
            context_id=context_id,
            task_type=task_type,
            payload={},
        )
        db.add(answer)

    answer.content_id = content_id
    answer.payload = payload
    answer.answered_at = datetime.now(timezone.utc)
    if file_id is not None:
        answer.file_id = file_id

    if checkers.is_objective(task_type):
        result = checkers.check_answer(task_type, payload, answer_key)
        answer.correct_count = result.correct_count
        answer.wrong_count = result.wrong_count
        answer.total_count = result.total_count
        answer.is_checked = True
        answer.auto_score = _correctness_percentage(result.correct_count, result.wrong_count)

    await db.flush()

    await emit_event(
        db,
        event_type="answer_updated",
        payload={
            "answer_id": str(answer.id),
            "task_id": str(task_id),
            "user_id": str(user_id),
            "context_type": context_type.value if isinstance(context_type, ContextType) else context_type,
            "context_id": str(context_id),
            "is_new": is_new,
            "auto_score": answer.auto_score,
            "manual_score": answer.manual_score,
        },
    )

    if (
        context_type == ContextType.assignment
        and checkers.is_objective(task_type)
        and answer.auto_score is not None
    ):
        await emit_event(
            db,
            event_type="answer_scored",
            payload={
                "session_id": str(context_id),
                "task_id": str(task_id),
                "correctness": answer.auto_score,
            },
        )

    return answer
