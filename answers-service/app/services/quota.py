import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Answer, AnswerFile, ContextType
from app.services.events import emit_event


async def get_answer_storage_bytes(
    db: AsyncSession, *, user_id: uuid.UUID, context_type: ContextType, context_id: uuid.UUID
) -> int:
    rows = (
        await db.execute(
            select(AnswerFile.size_bytes)
            .join(Answer, Answer.file_id == AnswerFile.id)
            .where(
                Answer.user_id == user_id,
                Answer.context_type == context_type,
                Answer.context_id == context_id,
            )
        )
    ).all()
    return sum(row[0] for row in rows)


async def enforce_answer_quota(
    db: AsyncSession, *, user_id: uuid.UUID, context_type: ContextType, context_id: uuid.UUID
) -> list[uuid.UUID]:
    """Same policy as the old system: once a student's answer files in this
    context exceed the limit, delete the OLDEST ones first until back under
    it - but unlike the old system, this is bounded (ordered, limited query,
    not a full unbounded fetch-then-sort in Python) and every deletion emits
    an 'answer_reset' event, so it's never a silent disappearance."""
    total = await get_answer_storage_bytes(
        db, user_id=user_id, context_type=context_type, context_id=context_id
    )
    if total <= settings.student_answer_limit_bytes:
        return []

    candidates = (
        await db.execute(
            select(Answer, AnswerFile.size_bytes)
            .join(AnswerFile, Answer.file_id == AnswerFile.id)
            .where(
                Answer.user_id == user_id,
                Answer.context_type == context_type,
                Answer.context_id == context_id,
            )
            .order_by(Answer.answered_at.asc())
        )
    ).all()

    deleted_ids: list[uuid.UUID] = []
    for answer, size_bytes in candidates:
        if total <= settings.student_answer_limit_bytes:
            break
        await emit_event(
            db,
            event_type="answer_reset",
            payload={
                "task_id": str(answer.task_id),
                "user_id": str(user_id),
                "context_type": context_type.value,
                "context_id": str(context_id),
                "reason": "student_answer_quota_exceeded",
            },
        )
        deleted_ids.append(answer.id)
        await db.delete(answer)
        total -= size_bytes

    await db.flush()
    return deleted_ids
