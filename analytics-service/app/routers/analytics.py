import uuid
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import CurrentAdmin, get_current_admin
from app.models import ExportJob, ExportStatus, ExportType
from app.schemas import (
    ExportJobCreate,
    ExportJobOut,
    LessonQualityDailyOut,
    LessonQualityReportOut,
    LessonReviewFlagCreate,
    LessonReviewFlagOut,
    LessonReviewFlagUpdate,
    PlatformOverviewDailyOut,
    PlatformOverviewOut,
    UserActivityDailyOut,
    UserActivityStatsOut,
)
from app.services import projections

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _default_date_range(
    date_from: date | None, date_to: date | None
) -> tuple[date, date]:
    end = date_to or date.today()
    start = date_from or (end - timedelta(days=29))
    if start > end:
        raise HTTPException(status_code=422, detail={"code": "invalid_date_range"})
    return start, end


def _validate_export_request(body: ExportJobCreate) -> None:
    if body.date_from and body.date_to and body.date_from > body.date_to:
        raise HTTPException(status_code=422, detail={"code": "invalid_date_range"})

    if body.export_type == ExportType.user_activity and body.user_id is None:
        raise HTTPException(status_code=422, detail={"code": "user_id_required"})

    if body.export_type == ExportType.lesson_quality and body.lesson_id is None:
        raise HTTPException(status_code=422, detail={"code": "lesson_id_required"})


@router.get("/users/{user_id}/activity", response_model=UserActivityStatsOut)
async def get_user_activity(
    user_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: CurrentAdmin = Depends(get_current_admin),
) -> UserActivityStatsOut:
    start, end = _default_date_range(date_from, date_to)
    rows = await projections.get_user_activity_stats(
        db, user_id=user_id, date_from=start, date_to=end
    )
    daily = [UserActivityDailyOut.model_validate(row, from_attributes=True) for row in rows]
    totals = {
        "guests_created": sum(row.guests_created for row in rows),
        "users_created": sum(row.users_created for row in rows),
        "lessons_created": sum(row.lessons_created for row in rows),
        "classrooms_created": sum(row.classrooms_created for row in rows),
        "assignments_created": sum(row.assignments_created for row in rows),
        "sessions_started": sum(row.sessions_started for row in rows),
        "sessions_submitted": sum(row.sessions_submitted for row in rows),
        "answers_submitted": sum(row.answers_submitted for row in rows),
        "feedback_submitted": sum(row.feedback_submitted for row in rows),
        "ai_jobs_requested": sum(row.ai_jobs_requested for row in rows),
        "ai_jobs_succeeded": sum(row.ai_jobs_succeeded for row in rows),
        "ai_jobs_failed": sum(row.ai_jobs_failed for row in rows),
        "ai_lessons_generated": sum(row.ai_lessons_generated for row in rows),
        "ai_images_generated": sum(row.ai_images_generated for row in rows),
        "ai_audio_generated": sum(row.ai_audio_generated for row in rows),
    }
    return UserActivityStatsOut(
        user_id=user_id,
        date_from=start,
        date_to=end,
        totals=totals,
        daily=daily,
    )


@router.get("/lessons/{lesson_id}/quality", response_model=LessonQualityReportOut)
async def get_lesson_quality(
    lesson_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: CurrentAdmin = Depends(get_current_admin),
) -> LessonQualityReportOut:
    start, end = _default_date_range(date_from, date_to)
    rows = await projections.get_lesson_quality_report(
        db, lesson_id=lesson_id, date_from=start, date_to=end
    )
    open_flags = await projections.count_open_flags(db, lesson_id=lesson_id)
    daily = [LessonQualityDailyOut.model_validate(row, from_attributes=True) for row in rows]
    score_count = sum(row.score_count for row in rows)
    score_sum = sum(row.score_sum for row in rows)
    totals = {
        "assignments_created": sum(row.assignments_created for row in rows),
        "sessions_started": sum(row.sessions_started for row in rows),
        "sessions_submitted": sum(row.sessions_submitted for row in rows),
        "answers_scored": sum(row.answers_scored for row in rows),
        "feedback_count": sum(row.feedback_count for row in rows),
        "feedback_rating_sum": sum(row.feedback_rating_sum for row in rows),
        "avg_score": round(score_sum / score_count, 2) if score_count else 0.0,
        "avg_feedback_rating": round(
            sum(row.feedback_rating_sum for row in rows)
            / max(sum(row.feedback_count for row in rows), 1),
            2,
        )
        if sum(row.feedback_count for row in rows)
        else 0.0,
    }
    return LessonQualityReportOut(
        lesson_id=lesson_id,
        date_from=start,
        date_to=end,
        totals=totals,
        open_flags=open_flags,
        daily=daily,
    )


@router.post("/lessons/{lesson_id}/flags", response_model=LessonReviewFlagOut)
async def create_lesson_flag(
    lesson_id: uuid.UUID,
    body: LessonReviewFlagCreate,
    db: AsyncSession = Depends(get_db),
    admin: CurrentAdmin = Depends(get_current_admin),
) -> LessonReviewFlagOut:
    flag = await projections.create_lesson_flag(
        db,
        lesson_id=lesson_id,
        created_by_user_id=admin.user_id,
        reason=body.reason,
        severity=body.severity,
    )
    return LessonReviewFlagOut.model_validate(flag, from_attributes=True)


@router.patch("/flags/{flag_id}", response_model=LessonReviewFlagOut)
async def update_lesson_flag(
    flag_id: uuid.UUID,
    body: LessonReviewFlagUpdate,
    db: AsyncSession = Depends(get_db),
    admin: CurrentAdmin = Depends(get_current_admin),
) -> LessonReviewFlagOut:
    flag = await projections.update_lesson_flag(
        db,
        flag_id=flag_id,
        resolved_by_user_id=admin.user_id,
        status=body.status,
        resolution_note=body.resolution_note,
    )
    if flag is None:
        raise HTTPException(status_code=404, detail={"code": "flag_not_found"})
    return LessonReviewFlagOut.model_validate(flag, from_attributes=True)


@router.get("/platform/overview", response_model=PlatformOverviewOut)
async def get_platform_overview(
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: CurrentAdmin = Depends(get_current_admin),
) -> PlatformOverviewOut:
    start, end = _default_date_range(date_from, date_to)
    rows = await projections.get_platform_overview(db, date_from=start, date_to=end)
    daily = [PlatformOverviewDailyOut.model_validate(row, from_attributes=True) for row in rows]
    totals = {
        "guests_created": sum(row.guests_created for row in rows),
        "users_created": sum(row.users_created for row in rows),
        "users_upgraded": sum(row.users_upgraded for row in rows),
        "lessons_created": sum(row.lessons_created for row in rows),
        "classrooms_created": sum(row.classrooms_created for row in rows),
        "assignments_created": sum(row.assignments_created for row in rows),
        "sessions_started": sum(row.sessions_started for row in rows),
        "sessions_submitted": sum(row.sessions_submitted for row in rows),
        "sessions_expired": sum(row.sessions_expired for row in rows),
        "answers_submitted": sum(row.answers_submitted for row in rows),
        "answers_scored": sum(row.answers_scored for row in rows),
        "feedback_submitted": sum(row.feedback_submitted for row in rows),
        "ai_jobs_requested": sum(row.ai_jobs_requested for row in rows),
        "ai_jobs_succeeded": sum(row.ai_jobs_succeeded for row in rows),
        "ai_jobs_failed": sum(row.ai_jobs_failed for row in rows),
        "ai_lessons_generated": sum(row.ai_lessons_generated for row in rows),
        "ai_images_generated": sum(row.ai_images_generated for row in rows),
        "ai_audio_generated": sum(row.ai_audio_generated for row in rows),
    }
    return PlatformOverviewOut(date_from=start, date_to=end, totals=totals, daily=daily)


@router.post("/exports", response_model=ExportJobOut)
async def create_export_job(
    body: ExportJobCreate,
    db: AsyncSession = Depends(get_db),
    admin: CurrentAdmin = Depends(get_current_admin),
) -> ExportJobOut:
    _validate_export_request(body)
    filters = {
        key: (value.isoformat() if hasattr(value, "isoformat") else str(value))
        for key, value in body.model_dump(exclude_none=True).items()
        if key != "export_type"
    }
    job = await projections.create_export_job(
        db,
        requested_by_user_id=admin.user_id,
        export_type=body.export_type,
        filters=filters,
    )
    return ExportJobOut.model_validate(job, from_attributes=True)


@router.get("/exports/{job_id}", response_model=ExportJobOut)
async def get_export_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: CurrentAdmin = Depends(get_current_admin),
) -> ExportJobOut:
    job = await db.get(ExportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "export_not_found"})
    return ExportJobOut.model_validate(job, from_attributes=True)


@router.get("/exports/{job_id}/download")
async def download_export(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: CurrentAdmin = Depends(get_current_admin),
):
    job = await db.get(ExportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "export_not_found"})
    if job.status == ExportStatus.failed:
        raise HTTPException(status_code=409, detail={"code": "export_failed"})
    if not job.storage_path:
        raise HTTPException(status_code=409, detail={"code": "export_not_ready"})
    if not Path(job.storage_path).exists():
        raise HTTPException(status_code=410, detail={"code": "export_file_missing"})
    return FileResponse(job.storage_path, filename=f"{job.id}.csv", media_type="text/csv")
