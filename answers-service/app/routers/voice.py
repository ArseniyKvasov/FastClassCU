import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import CurrentUser, get_current_user
from app.models import ContextType
from app.redis_client import get_redis
from app.schemas import AnswerOut
from app.services import answers as answers_svc
from app.services import files as files_svc
from app.services.quota import enforce_answer_quota

router = APIRouter(prefix="/answers", tags=["voice"])


@router.post("/voice", response_model=AnswerOut)
async def submit_voice_answer(
    task_id: uuid.UUID = Form(...),
    context_type: ContextType = Form(...),
    context_id: uuid.UUID = Form(...),
    duration_seconds: float | None = Form(default=None),
    audio: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    r=Depends(get_redis),
):
    data = await audio.read()
    file_row = await files_svc.create_answer_file(
        db, data=data, mime_type=audio.content_type, duration_seconds=duration_seconds
    )

    try:
        answer = await answers_svc.submit_answer(
            db,
            r,
            task_id=task_id,
            user_id=user.user_id,
            context_type=context_type,
            context_id=context_id,
            payload={"file_id": str(file_row.id), "duration_seconds": duration_seconds},
            file_id=file_row.id,
        )
    except answers_svc.content_client.AnswerKeyNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "task_not_found"})

    await enforce_answer_quota(
        db, user_id=user.user_id, context_type=context_type, context_id=context_id
    )
    await db.commit()
    return answer
