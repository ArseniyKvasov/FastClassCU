import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session_factory
from app.models import GenerationJob, JobStatus
from app.services import events as events_svc, workflows

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def claim_jobs(db: AsyncSession) -> list[str]:
    rows = (
        await db.scalars(
            select(GenerationJob)
            .where(
                GenerationJob.status == JobStatus.pending,
                GenerationJob.cancel_requested.is_(False),
            )
            .order_by(GenerationJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(settings.worker_batch_size)
        )
    ).all()
    claimed_ids: list[str] = []
    for job in rows:
        job.status = JobStatus.running
        job.started_at = _now()
        job.attempts += 1
        claimed_ids.append(str(job.id))
    await db.flush()
    return claimed_ids


async def process_claimed_job(job_id: str) -> None:
    async with get_session_factory()() as db:
        job = await workflows.hydrate_job(db, job_id=job_id)
        if job is None:
            return
        try:
            if job.cancel_requested:
                job.status = JobStatus.cancelled
            else:
                await workflows.process_job(db, job=job)
        except Exception as exc:  # noqa: BLE001
            logger.exception("generation job failed", extra={"job_id": job_id})
            job.error_code = "generation_failed"
            job.error_message = str(exc)
            if job.attempts < job.max_attempts and not job.cancel_requested:
                job.status = JobStatus.pending
            else:
                job.status = JobStatus.failed
                job.finished_at = _now()
                await events_svc.emit_event(
                    db,
                    event_type="generation_failed",
                    payload={
                        "job_id": str(job.id),
                        "requester_id": str(job.requester_id),
                        "intent": job.intent.value,
                        "error_code": job.error_code,
                    },
                )
        else:
            if job.status in {JobStatus.succeeded, JobStatus.cancelled}:
                job.finished_at = _now()
        await db.commit()


async def run_worker(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        async with get_session_factory()() as db:
            async with db.begin():
                job_ids = await claim_jobs(db)
        for job_id in job_ids:
            await process_claimed_job(job_id)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=settings.worker_poll_interval_seconds)
        except TimeoutError:
            continue
