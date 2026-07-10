import csv
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ExportJob, ExportStatus, ExportType, LessonReviewFlag
from app.services import projections


def _ensure_storage_dir() -> Path:
    root = Path(settings.export_storage_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _serialize_rows(path: Path, rows: list[dict]) -> int:
    if not rows:
        path.write_text("")
        return 0

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _coerce_date(raw: str | None) -> date | None:
    if not raw:
        return None
    return date.fromisoformat(raw)


async def build_export_rows(db: AsyncSession, *, job: ExportJob) -> list[dict]:
    filters = dict(job.filters or {})
    date_from = _coerce_date(filters.get("date_from"))
    date_to = _coerce_date(filters.get("date_to"))

    if job.export_type == ExportType.user_activity:
        user_id = uuid.UUID(filters["user_id"])
        items = await projections.get_user_activity_stats(
            db,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
        )
        return [
            {
                "activity_date": item.activity_date.isoformat(),
                "user_id": str(item.user_id),
                "guests_created": item.guests_created,
                "users_created": item.users_created,
                "lessons_created": item.lessons_created,
                "classrooms_created": item.classrooms_created,
                "assignments_created": item.assignments_created,
                "sessions_started": item.sessions_started,
                "sessions_submitted": item.sessions_submitted,
                "answers_submitted": item.answers_submitted,
                "feedback_submitted": item.feedback_submitted,
                "ai_jobs_requested": item.ai_jobs_requested,
                "ai_jobs_succeeded": item.ai_jobs_succeeded,
                "ai_jobs_failed": item.ai_jobs_failed,
                "ai_lessons_generated": item.ai_lessons_generated,
                "ai_images_generated": item.ai_images_generated,
                "ai_audio_generated": item.ai_audio_generated,
            }
            for item in items
        ]

    if job.export_type == ExportType.lesson_quality:
        lesson_id = uuid.UUID(filters["lesson_id"])
        items = await projections.get_lesson_quality_report(
            db,
            lesson_id=lesson_id,
            date_from=date_from,
            date_to=date_to,
        )
        return [
            {
                "activity_date": item.activity_date.isoformat(),
                "lesson_id": str(item.lesson_id),
                "assignments_created": item.assignments_created,
                "sessions_started": item.sessions_started,
                "sessions_submitted": item.sessions_submitted,
                "answers_scored": item.answers_scored,
                "score_sum": item.score_sum,
                "score_count": item.score_count,
                "feedback_count": item.feedback_count,
                "feedback_rating_sum": item.feedback_rating_sum,
            }
            for item in items
        ]

    if job.export_type == ExportType.platform_overview:
        items = await projections.get_platform_overview(
            db,
            date_from=date_from,
            date_to=date_to,
        )
        return [
            {
                "activity_date": item.activity_date.isoformat(),
                "guests_created": item.guests_created,
                "users_created": item.users_created,
                "users_upgraded": item.users_upgraded,
                "lessons_created": item.lessons_created,
                "classrooms_created": item.classrooms_created,
                "assignments_created": item.assignments_created,
                "sessions_started": item.sessions_started,
                "sessions_submitted": item.sessions_submitted,
                "sessions_expired": item.sessions_expired,
                "answers_submitted": item.answers_submitted,
                "answers_scored": item.answers_scored,
                "feedback_submitted": item.feedback_submitted,
                "ai_jobs_requested": item.ai_jobs_requested,
                "ai_jobs_succeeded": item.ai_jobs_succeeded,
                "ai_jobs_failed": item.ai_jobs_failed,
                "ai_lessons_generated": item.ai_lessons_generated,
                "ai_images_generated": item.ai_images_generated,
                "ai_audio_generated": item.ai_audio_generated,
            }
            for item in items
        ]

    if job.export_type == ExportType.lesson_flags:
        stmt = select(LessonReviewFlag).order_by(LessonReviewFlag.created_at.desc())
        if filters.get("lesson_id"):
            stmt = stmt.where(LessonReviewFlag.lesson_id == uuid.UUID(filters["lesson_id"]))
        items = list((await db.scalars(stmt)).all())
        return [
            {
                "flag_id": str(item.id),
                "lesson_id": str(item.lesson_id),
                "created_by_user_id": str(item.created_by_user_id),
                "reason": item.reason,
                "severity": item.severity,
                "status": item.status,
                "resolution_note": item.resolution_note or "",
                "created_at": item.created_at.isoformat(),
                "resolved_at": item.resolved_at.isoformat() if item.resolved_at else "",
            }
            for item in items
        ]

    raise ValueError(f"unsupported_export_type:{job.export_type}")


async def run_export_job(db: AsyncSession, *, job: ExportJob) -> ExportJob:
    rows = await build_export_rows(db, job=job)
    if len(rows) > settings.export_max_rows:
        raise ValueError(f"export_too_large:{len(rows)}>{settings.export_max_rows}")

    target = _ensure_storage_dir() / f"{job.id}.csv"
    row_count = _serialize_rows(target, rows)

    job.status = ExportStatus.completed
    job.storage_path = str(target)
    job.row_count = row_count
    return job
