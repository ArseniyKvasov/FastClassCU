from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas import GcReport
from app.services import gc as gc_svc

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/gc", response_model=GcReport)
async def run_gc(db: AsyncSession = Depends(get_db)) -> dict:
    """Manual trigger for the orphan reaper. In production this is a
    scheduled job (cron/Celery beat), not a public endpoint - gate this
    behind internal auth before exposing it past localhost."""
    report = await gc_svc.run_gc(db)
    await db.commit()
    return report
