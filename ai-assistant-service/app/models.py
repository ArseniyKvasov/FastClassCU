from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JobIntent(str, enum.Enum):
    create_lesson = "create_lesson"
    adapt_lesson = "adapt_lesson"
    generate_image = "generate_image"
    generate_audio = "generate_audio"


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class ArtifactType(str, enum.Enum):
    lesson_draft = "lesson_draft"
    image = "image"
    audio = "audio"
    bundle = "bundle"


class MemoryKind(str, enum.Enum):
    profile = "profile"
    feedback = "feedback"
    preference = "preference"


class ProviderCallStatus(str, enum.Enum):
    succeeded = "succeeded"
    failed = "failed"


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    requester_id: Mapped[uuid.UUID] = mapped_column(index=True)
    intent: Mapped[JobIntent] = mapped_column(String(32), index=True)
    status: Mapped[JobStatus] = mapped_column(String(16), default=JobStatus.pending, index=True)
    input_payload: Mapped[dict] = mapped_column(JSONB)
    context_payload: Mapped[dict] = mapped_column(JSONB, nullable=True)
    result_payload: Mapped[dict] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class GenerationArtifact(Base):
    __tablename__ = "generation_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("generation_jobs.id", ondelete="CASCADE"), index=True
    )
    artifact_type: Mapped[ArtifactType] = mapped_column(String(32))
    content_service_file_id: Mapped[uuid.UUID] = mapped_column(nullable=True)
    lesson_id: Mapped[uuid.UUID] = mapped_column(nullable=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ProviderCall(Base):
    __tablename__ = "provider_calls"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("generation_jobs.id", ondelete="CASCADE"), index=True
    )
    provider_name: Mapped[str] = mapped_column(String(64), index=True)
    operation: Mapped[str] = mapped_column(String(64))
    status: Mapped[ProviderCallStatus] = mapped_column(String(16))
    request_summary: Mapped[dict] = mapped_column(JSONB, nullable=True)
    response_summary: Mapped[dict] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MemoryItem(Base):
    __tablename__ = "memory_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    kind: Mapped[MemoryKind] = mapped_column(String(32), index=True)
    scope: Mapped[str] = mapped_column(String(64), default="global")
    content: Mapped[dict] = mapped_column(JSONB)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class StyleProfile(Base):
    __tablename__ = "style_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    profile: Mapped[dict] = mapped_column(JSONB)
    source_lesson_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class AIAssistantEvent(Base):
    __tablename__ = "ai_assistant_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
