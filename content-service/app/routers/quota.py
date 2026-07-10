import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.schemas import QuotaOut
from app.services import content as content_svc

router = APIRouter(prefix="/quota", tags=["quota"])


@router.get("/{teacher_id}", response_model=QuotaOut)
async def get_quota(teacher_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    bytes_used = await content_svc.teacher_storage_bytes(db, teacher_id)
    return {
        "teacher_id": teacher_id,
        "storage_bytes": bytes_used,
        "limit_bytes": settings.teacher_storage_limit_bytes,
    }
