import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import ExportJob, ExportStatus
from app.services import exports

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def claim_job() -> str | None:
    async with SessionLocal() as db:
        row = await db.scalar(
            select(ExportJob)
            .where(ExportJob.status == ExportStatus.pending)
            .order_by(ExportJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return None
        row.status = ExportStatus.running
        row.started_at = _now()
        await db.commit()
        return str(row.id)


async def process_job(job_id: str) -> None:
    async with SessionLocal() as db:
        job = await db.get(ExportJob, job_id)
        if job is None:
            return
        try:
            await exports.run_export_job(db, job=job)
        except Exception as exc:  # noqa: BLE001
            logger.exception("analytics export failed", extra={"job_id": job_id})
            job.status = ExportStatus.failed
            job.error_message = str(exc)
        finally:
            job.finished_at = _now()
            await db.commit()


async def run_worker(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        job_id = await claim_job()
        if job_id:
            await process_job(job_id)
            continue
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=settings.export_worker_poll_interval_seconds)
        except TimeoutError:
            continue
