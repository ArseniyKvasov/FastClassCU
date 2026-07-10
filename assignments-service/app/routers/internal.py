import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.redis_client import get_redis
from app.services import grading as grading_svc
from app.ws.manager import publish
from fastclass_shared.auth import ServiceAuthError, authenticate_service_request

router = APIRouter(prefix="/internal", tags=["internal"])


def require_assignments_answer_scored_write(
    authorization: str | None = Header(default=None),
    x_service_token: str | None = Header(default=None),
) -> None:
    try:
        authenticate_service_request(
            authorization=authorization,
            x_service_token=x_service_token,
            public_key_path=settings.jwt_public_key_path,
            issuer=settings.jwt_issuer,
            required_scopes={"assignments:answer-scored:write"},
            allow_legacy_token=settings.allow_legacy_internal_service_token,
            legacy_token=settings.internal_service_token,
        )
    except ServiceAuthError:
        raise HTTPException(status_code=401, detail={"code": "invalid_service_token"})


class AnswerScoredEvent(BaseModel):
    session_id: uuid.UUID
    task_id: uuid.UUID
    correctness: float


@router.post("/events/answer-scored")
async def answer_scored(
    body: AnswerScoredEvent,
    db: AsyncSession = Depends(get_db),
    r=Depends(get_redis),
    _auth: None = Depends(require_assignments_answer_scored_write),
) -> dict:
    session = await grading_svc.apply_answer_scored(
        db, session_id=body.session_id, task_id=body.task_id, correctness=body.correctness
    )
    await db.commit()

    if session is not None and session.grade is not None:
        await publish(
            r,
            assignment_id=session.assignment_id,
            message={
                "type": "session_grade_changed",
                "session_id": str(session.id),
                "grade": float(session.grade),
            },
        )
    return {"applied": session is not None}
