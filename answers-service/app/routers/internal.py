import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import ContextType
from app.redis_client import get_redis
from app.schemas import AnswerOut
from app.services import answers as answers_svc
from app.services import content_client
from fastclass_shared.auth import ServiceAuthError, authenticate_service_request

router = APIRouter(prefix="/internal", tags=["internal"])


def require_service_token(
    authorization: str | None = Header(default=None),
    x_service_token: str | None = Header(default=None),
    required_scopes: set[str] | None = None,
) -> None:
    try:
        authenticate_service_request(
            authorization=authorization,
            x_service_token=x_service_token,
            public_key_path=settings.jwt_public_key_path,
            issuer=settings.jwt_issuer,
            required_scopes=required_scopes,
            allow_legacy_token=settings.allow_legacy_internal_service_token,
            legacy_token=settings.internal_service_token,
        )
    except ServiceAuthError:
        raise HTTPException(status_code=401, detail={"code": "invalid_service_token"})


def require_answers_collab_snapshot_write(
    authorization: str | None = Header(default=None),
    x_service_token: str | None = Header(default=None),
) -> None:
    require_service_token(
        authorization=authorization,
        x_service_token=x_service_token,
        required_scopes={"answers:collab-snapshot:write"},
    )


def require_answers_cache_invalidate_write(
    authorization: str | None = Header(default=None),
    x_service_token: str | None = Header(default=None),
) -> None:
    require_service_token(
        authorization=authorization,
        x_service_token=x_service_token,
        required_scopes={"answers:cache-invalidate:write"},
    )


class CollabSnapshot(BaseModel):
    task_id: uuid.UUID
    user_id: uuid.UUID
    context_type: ContextType
    context_id: uuid.UUID
    document_json: dict | None = None
    plain_text: str | None = None
    text: str | None = None
    revision: int


@router.get("/collab-snapshot", response_model=AnswerOut)
async def get_collab_snapshot(
    task_id: uuid.UUID,
    user_id: uuid.UUID,
    context_type: ContextType,
    context_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(require_answers_collab_snapshot_write),
):
    answer = await answers_svc.get_answer(
        db,
        task_id=task_id,
        user_id=user_id,
        context_type=context_type,
        context_id=context_id,
    )
    if answer is None:
        raise HTTPException(status_code=404, detail={"code": "answer_not_found"})
    return answer


@router.post("/collab-snapshot", response_model=AnswerOut)
async def receive_collab_snapshot(
    body: CollabSnapshot,
    db: AsyncSession = Depends(get_db),
    r=Depends(get_redis),
    _auth: None = Depends(require_answers_collab_snapshot_write),
):
    """Collaboration Service calls this periodically (and on session close)
    to persist the current text of a writing-task CRDT document. The live
    document itself never lives here - this is just the durable snapshot,
    same split as Content Service's TaskContent vs the in-memory CRDT state."""
    try:
        answer = await answers_svc.submit_answer(
            db,
            r,
            task_id=body.task_id,
            user_id=body.user_id,
            context_type=body.context_type,
            context_id=body.context_id,
            payload={
                "document_json": body.document_json,
                "plain_text": body.plain_text if body.plain_text is not None else body.text or "",
                "text": body.text if body.text is not None else body.plain_text or "",
                "revision": body.revision,
            },
        )
    except content_client.AnswerKeyNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "task_not_found"})

    await db.commit()
    return answer


class TaskUpdatedEvent(BaseModel):
    task_id: uuid.UUID


@router.post("/events/task-updated")
async def task_updated(
    body: TaskUpdatedEvent,
    r=Depends(get_redis),
    _auth: None = Depends(require_answers_cache_invalidate_write),
) -> dict:
    """Consumes Content Service's 'task_updated' event (via whatever relay
    forwards outbox events - see Content Service's content_events table) to
    drop our cached answer-key, since the task now points at a different
    content_id."""
    await content_client.invalidate_answer_key(r, task_id=body.task_id)
    return {"invalidated": True}
