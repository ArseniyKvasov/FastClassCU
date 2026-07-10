import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import ExportStatus, ExportType, FlagSeverity, FlagStatus


class UserActivityDailyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    activity_date: date
    guests_created: int
    users_created: int
    lessons_created: int
    classrooms_created: int
    assignments_created: int
    sessions_started: int
    sessions_submitted: int
    answers_submitted: int
    feedback_submitted: int
    ai_jobs_requested: int
    ai_jobs_succeeded: int
    ai_jobs_failed: int
    ai_lessons_generated: int
    ai_images_generated: int
    ai_audio_generated: int


class UserActivityStatsOut(BaseModel):
    user_id: uuid.UUID
    date_from: date
    date_to: date
    totals: dict[str, int]
    daily: list[UserActivityDailyOut]


class LessonQualityDailyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    activity_date: date
    assignments_created: int
    sessions_started: int
    sessions_submitted: int
    answers_scored: int
    score_sum: float
    score_count: int
    feedback_count: int
    feedback_rating_sum: int


class LessonQualityReportOut(BaseModel):
    lesson_id: uuid.UUID
    date_from: date
    date_to: date
    totals: dict[str, float | int]
    open_flags: int
    daily: list[LessonQualityDailyOut]


class LessonReviewFlagCreate(BaseModel):
    reason: str = Field(min_length=3)
    severity: FlagSeverity = FlagSeverity.medium


class LessonReviewFlagUpdate(BaseModel):
    status: FlagStatus
    resolution_note: str | None = None


class LessonReviewFlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lesson_id: uuid.UUID
    created_by_user_id: uuid.UUID
    reason: str
    severity: FlagSeverity
    status: FlagStatus
    resolution_note: str | None = None
    resolved_by_user_id: uuid.UUID | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class PlatformOverviewDailyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    activity_date: date
    guests_created: int
    users_created: int
    users_upgraded: int
    lessons_created: int
    classrooms_created: int
    assignments_created: int
    sessions_started: int
    sessions_submitted: int
    sessions_expired: int
    answers_submitted: int
    answers_scored: int
    feedback_submitted: int
    ai_jobs_requested: int
    ai_jobs_succeeded: int
    ai_jobs_failed: int
    ai_lessons_generated: int
    ai_images_generated: int
    ai_audio_generated: int


class PlatformOverviewOut(BaseModel):
    date_from: date
    date_to: date
    totals: dict[str, int]
    daily: list[PlatformOverviewDailyOut]


class ExportJobCreate(BaseModel):
    export_type: ExportType
    date_from: date | None = None
    date_to: date | None = None
    user_id: uuid.UUID | None = None
    lesson_id: uuid.UUID | None = None


class ExportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requested_by_user_id: uuid.UUID
    export_type: ExportType
    status: ExportStatus
    filters: dict
    storage_path: str | None = None
    row_count: int | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
