import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TargetType(str, enum.Enum):
    link = "link"
    classroom = "classroom"


class SessionStatus(str, enum.Enum):
    active = "active"
    submitted = "submitted"
    expired = "expired"
    checked = "checked"
    revision = "revision"


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    teacher_id: Mapped[uuid.UUID] = mapped_column(index=True)
    lesson_id: Mapped[uuid.UUID] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(255))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempts_limit: Mapped[int] = mapped_column(Integer, default=1)
    show_results_immediately: Mapped[bool] = mapped_column(Boolean, default=True)
    target_type: Mapped[TargetType] = mapped_column(String(16))
    # Populated only when target_type == classroom; a plain reference (no
    # cross-service FK) to a Classroom Service classroom id.
    target_classroom_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class AssignmentTask(Base):
    __tablename__ = "assignment_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), index=True
    )
    # Reference into Content Service - no cross-service FK, just an id.
    task_id: Mapped[uuid.UUID] = mapped_column()
    position: Mapped[int] = mapped_column(Integer, default=0)
    weight: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("assignment_id", "task_id", name="uq_assignment_task"),
    )


class AssignmentSession(Base):
    __tablename__ = "assignment_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[SessionStatus] = mapped_column(String(16), default=SessionStatus.active)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Saved aggregate, recomputed from Answers Service's answer_scored events
    # - never recalculated live on every read (the old system's approach).
    grade: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    # Once a teacher manually sets a grade, the auto-aggregation consumer
    # (services/grading.py) must never overwrite it again.
    grade_overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    teacher_comment: Mapped[str] = mapped_column(Text, default="")
    teacher_comment_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "assignment_id", "student_id", "attempt_number", name="uq_assignment_student_attempt"
        ),
    )


class TaskScore(Base):
    """One row per (session, task) - the per-task correctness/weight inputs
    that get aggregated into AssignmentSession.grade. Populated by consuming
    Answers Service's 'answer_scored' events, never by Assignments Service
    grading anything itself."""

    __tablename__ = "task_scores"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assignment_sessions.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column()
    correctness: Mapped[float] = mapped_column(Numeric(5, 2))  # 0..100
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint("session_id", "task_id", name="uq_session_task_score"),
    )


class AssignmentEvent(Base):
    """Transactional outbox - same pattern as every other service."""

    __tablename__ = "assignment_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConsumedEvent(Base):
    """Per-consumer idempotency ledger for Redis Streams delivery."""

    __tablename__ = "consumed_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    consumer_name: Mapped[str] = mapped_column(String(128), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        UniqueConstraint("event_id", "consumer_name", name="uq_consumed_event_consumer"),
    )
