import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ContextType(str, enum.Enum):
    classroom = "classroom"
    assignment = "assignment"


class AnswerFile(Base):
    """Content-addressable, same pattern as Content Service's FileAsset - a
    separate store because answer files (voice recordings) have a different
    lifecycle/owner than lesson materials, even though the mechanism is
    identical."""

    __tablename__ = "answer_files"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    storage_key: Mapped[str] = mapped_column(String(512))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Answer(Base):
    """One table for every task type, unlike the old system's 10 separate
    Django models - the payload shape is validated/normalized by the checker
    registry (app/checkers.py), not by having a dedicated column set per
    type. context_type+context_id replaces the old (classroom, nullable) +
    (assignment_session, nullable) dual-FK - a live-classroom answer and a
    homework answer for the same task+student are still two different rows,
    just expressed as one polymorphic key instead of two nullable FKs."""

    __tablename__ = "answers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(index=True)
    # The content_id the payload was checked against - lets us tell a cached
    # answer-key is stale if the task was edited since (see checkers/keys.py).
    content_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    context_type: Mapped[ContextType] = mapped_column(String(16))
    context_id: Mapped[uuid.UUID] = mapped_column(index=True)
    task_type: Mapped[str] = mapped_column(String(64))

    payload: Mapped[dict] = mapped_column(JSONB)

    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)

    # One manual-score field, not two (the old system had override_score on
    # the base model AND a separate manual_score on writing/voice answers).
    auto_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    manual_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    is_checked: Mapped[bool] = mapped_column(Boolean, default=False)

    file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("answer_files.id"), nullable=True
    )

    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "task_id", "user_id", "context_type", "context_id", name="uq_answer_identity"
        ),
    )


class AnswerEvent(Base):
    """Transactional outbox - same pattern as every other service."""

    __tablename__ = "answer_events"

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
