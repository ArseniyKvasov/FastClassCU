import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MembershipRole(str, enum.Enum):
    teacher = "teacher"
    student = "student"


class Classroom(Base):
    __tablename__ = "classrooms"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    teacher_id: Mapped[uuid.UUID] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(255))
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    is_preview: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class ClassroomSettings(Base):
    __tablename__ = "classroom_settings"

    classroom_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("classrooms.id", ondelete="CASCADE"), primary_key=True
    )
    communication_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    whiteboard_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    copying_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # One field, one type, decided up front: always a hash, never plaintext.
    # (The old system's join_password column ambiguously held either.)
    join_password_hash: Mapped[str] = mapped_column(String(255))
    join_password_set_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    classroom_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("classrooms.id", ondelete="CASCADE"), index=True
    )
    # Identity comes from the Auth Service JWT `sub` claim - never from a
    # name match. This is what closes the old system's account-takeover gap.
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[MembershipRole] = mapped_column(String(16))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (UniqueConstraint("classroom_id", "user_id", name="uq_classroom_user"),)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    classroom_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("classrooms.id", ondelete="CASCADE"), index=True
    )
    sender_id: Mapped[uuid.UUID] = mapped_column()
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ClassroomEvent(Base):
    """Transactional outbox - same pattern as Content Service's content_events.
    Analytics Service (and anyone else) consumes from here, not from direct
    calls into this service's internals."""

    __tablename__ = "classroom_events"

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
