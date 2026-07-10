import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FlagSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class FlagStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"


class ExportType(str, enum.Enum):
    user_activity = "user_activity"
    lesson_quality = "lesson_quality"
    platform_overview = "platform_overview"
    lesson_flags = "lesson_flags"


class ExportStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    producer: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ConsumedEvent(Base):
    __tablename__ = "consumed_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    consumer_name: Mapped[str] = mapped_column(String(128), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        UniqueConstraint("event_id", "consumer_name", name="uq_consumed_event_consumer"),
    )


class AssignmentDimension(Base):
    __tablename__ = "assignment_dimensions"

    assignment_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_classroom_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class SessionDimension(Base):
    __tablename__ = "session_dimensions"

    session_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    student_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class UserActivityDaily(Base):
    __tablename__ = "user_activity_daily"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    activity_date: Mapped[date] = mapped_column(Date, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    guests_created: Mapped[int] = mapped_column(Integer, default=0)
    users_created: Mapped[int] = mapped_column(Integer, default=0)
    lessons_created: Mapped[int] = mapped_column(Integer, default=0)
    classrooms_created: Mapped[int] = mapped_column(Integer, default=0)
    assignments_created: Mapped[int] = mapped_column(Integer, default=0)
    sessions_started: Mapped[int] = mapped_column(Integer, default=0)
    sessions_submitted: Mapped[int] = mapped_column(Integer, default=0)
    answers_submitted: Mapped[int] = mapped_column(Integer, default=0)
    feedback_submitted: Mapped[int] = mapped_column(Integer, default=0)
    ai_jobs_requested: Mapped[int] = mapped_column(Integer, default=0)
    ai_jobs_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    ai_jobs_failed: Mapped[int] = mapped_column(Integer, default=0)
    ai_lessons_generated: Mapped[int] = mapped_column(Integer, default=0)
    ai_images_generated: Mapped[int] = mapped_column(Integer, default=0)
    ai_audio_generated: Mapped[int] = mapped_column(Integer, default=0)
    last_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        UniqueConstraint("activity_date", "user_id", name="uq_user_activity_day"),
    )


class LessonQualityDaily(Base):
    __tablename__ = "lesson_quality_daily"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    activity_date: Mapped[date] = mapped_column(Date, index=True)
    lesson_id: Mapped[uuid.UUID] = mapped_column(index=True)
    assignments_created: Mapped[int] = mapped_column(Integer, default=0)
    sessions_started: Mapped[int] = mapped_column(Integer, default=0)
    sessions_submitted: Mapped[int] = mapped_column(Integer, default=0)
    answers_scored: Mapped[int] = mapped_column(Integer, default=0)
    score_sum: Mapped[float] = mapped_column(Float, default=0.0)
    score_count: Mapped[int] = mapped_column(Integer, default=0)
    feedback_count: Mapped[int] = mapped_column(Integer, default=0)
    feedback_rating_sum: Mapped[int] = mapped_column(Integer, default=0)
    last_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        UniqueConstraint("activity_date", "lesson_id", name="uq_lesson_quality_day"),
    )


class PlatformOverviewDaily(Base):
    __tablename__ = "platform_overview_daily"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    activity_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    guests_created: Mapped[int] = mapped_column(Integer, default=0)
    users_created: Mapped[int] = mapped_column(Integer, default=0)
    users_upgraded: Mapped[int] = mapped_column(Integer, default=0)
    lessons_created: Mapped[int] = mapped_column(Integer, default=0)
    classrooms_created: Mapped[int] = mapped_column(Integer, default=0)
    assignments_created: Mapped[int] = mapped_column(Integer, default=0)
    sessions_started: Mapped[int] = mapped_column(Integer, default=0)
    sessions_submitted: Mapped[int] = mapped_column(Integer, default=0)
    sessions_expired: Mapped[int] = mapped_column(Integer, default=0)
    answers_submitted: Mapped[int] = mapped_column(Integer, default=0)
    answers_scored: Mapped[int] = mapped_column(Integer, default=0)
    feedback_submitted: Mapped[int] = mapped_column(Integer, default=0)
    ai_jobs_requested: Mapped[int] = mapped_column(Integer, default=0)
    ai_jobs_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    ai_jobs_failed: Mapped[int] = mapped_column(Integer, default=0)
    ai_lessons_generated: Mapped[int] = mapped_column(Integer, default=0)
    ai_images_generated: Mapped[int] = mapped_column(Integer, default=0)
    ai_audio_generated: Mapped[int] = mapped_column(Integer, default=0)
    last_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LessonReviewFlag(Base):
    __tablename__ = "lesson_review_flags"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lesson_id: Mapped[uuid.UUID] = mapped_column(index=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    reason: Mapped[str] = mapped_column(Text)
    severity: Mapped[FlagSeverity] = mapped_column(String(16), default=FlagSeverity.medium)
    status: Mapped[FlagStatus] = mapped_column(String(16), default=FlagStatus.open, index=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    export_type: Mapped[ExportType] = mapped_column(String(32), index=True)
    status: Mapped[ExportStatus] = mapped_column(String(16), default=ExportStatus.pending, index=True)
    filters: Mapped[dict] = mapped_column(JSONB, default=dict)
    storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
