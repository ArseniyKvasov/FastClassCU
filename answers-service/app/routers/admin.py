from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.gc import collect_orphaned_files

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/gc")
async def run_gc(db: AsyncSession = Depends(get_db)) -> dict:
    """Manual trigger - in production this is a scheduled job, not a public
    endpoint (same caveat as Content Service's /admin/gc)."""
    reclaimed = await collect_orphaned_files(db)
    await db.commit()
    return {"reclaimed_files": len(reclaimed)}
