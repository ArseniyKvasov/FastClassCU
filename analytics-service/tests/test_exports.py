import csv
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import ExportJob, ExportStatus, ExportType, UserActivityDaily
from app.services import exports
from app.services.export_worker import process_job


async def test_run_export_job_writes_csv(db_session):
    user_id = uuid.uuid4()
    db_session.add(
        UserActivityDaily(
            activity_date=date(2026, 7, 9),
            user_id=user_id,
            ai_jobs_requested=2,
            ai_jobs_succeeded=1,
            ai_images_generated=1,
        )
    )
    job = ExportJob(
        requested_by_user_id=uuid.uuid4(),
        export_type=ExportType.user_activity,
        status=ExportStatus.running,
        filters={"user_id": str(user_id), "date_from": "2026-07-01", "date_to": "2026-07-31"},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    await exports.run_export_job(db_session, job=job)
    await db_session.commit()
    await db_session.refresh(job)

    assert job.status == ExportStatus.completed
    assert job.row_count == 1
    assert job.storage_path is not None

    with Path(job.storage_path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 1
    assert rows[0]["user_id"] == str(user_id)
    assert rows[0]["ai_jobs_requested"] == "2"
    assert rows[0]["ai_images_generated"] == "1"


async def test_process_job_marks_failure_for_invalid_filters(db_session):
    job = ExportJob(
        requested_by_user_id=uuid.uuid4(),
        export_type=ExportType.user_activity,
        status=ExportStatus.pending,
        filters={},
    )
    db_session.add(job)
    await db_session.commit()
    job_id = str(job.id)

    await process_job(job_id)

    async with SessionLocal() as verification_db:
        refreshed = await verification_db.scalar(select(ExportJob).where(ExportJob.id == job.id))
    assert refreshed is not None
    assert refreshed.status == ExportStatus.failed
    assert refreshed.error_message is not None
    assert refreshed.finished_at is not None
