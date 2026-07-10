import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models import ArtifactType, JobIntent, JobStatus


class LessonTaskFileRef(BaseModel):
    id: uuid.UUID
    mime_type: str | None = None
    original_filename: str | None = None


class LessonBundleTask(BaseModel):
    task_type: str
    payload: dict[str, Any]
    file_id: uuid.UUID | None = None
    position: int = 0
    file: LessonTaskFileRef | None = None


class LessonBundleSection(BaseModel):
    title: str = ""
    position: int = 0
    tasks: list[LessonBundleTask] = Field(default_factory=list)


class LessonBundle(BaseModel):
    owner_id: uuid.UUID
    title: str
    description: str | None = None
    sections: list[LessonBundleSection]


class LessonBundleOut(LessonBundle):
    id: uuid.UUID
    created_at: datetime


class TaskRegistryItem(BaseModel):
    task_type: str
    has_file: bool
    allowed_mime_types: tuple[str, ...]


class TaskRegistryOut(BaseModel):
    tasks: list[TaskRegistryItem]


class SourceAttachment(BaseModel):
    file_name: str
    mime_type: str
    content_base64: str | None = None
    content_text: str | None = None


class LessonDraftRequest(BaseModel):
    title: str
    description: str | None = None
    subject: str | None = None
    target_age: str | None = None
    language: str | None = None
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    source_attachments: list[SourceAttachment] = Field(default_factory=list)


class AdaptLessonRequest(BaseModel):
    lesson_id: uuid.UUID
    title: str | None = None
    description: str | None = None
    adaptation_goal: str
    target_age: str | None = None
    language: str | None = None
    constraints: list[str] = Field(default_factory=list)
    source_attachments: list[SourceAttachment] = Field(default_factory=list)


class ImageGenerationRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"
    negative_prompt: str | None = None
    lesson_id: uuid.UUID | None = None
    filename: str = "generated-image.png"


class AudioGenerationRequest(BaseModel):
    script: str
    title: str | None = None
    voice_mapping: dict[str, str] = Field(default_factory=dict)
    sample_context: str | None = None
    filename: str = "generated-audio.wav"


class GenerationArtifactOut(BaseModel):
    id: uuid.UUID
    artifact_type: ArtifactType
    content_service_file_id: uuid.UUID | None = None
    lesson_id: uuid.UUID | None = None
    mime_type: str | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class GenerationJobOut(BaseModel):
    id: uuid.UUID
    requester_id: uuid.UUID
    intent: JobIntent
    status: JobStatus
    input_payload: dict[str, Any]
    context_payload: dict[str, Any] | None = None
    result_payload: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    attempts: int
    max_attempts: int
    cancel_requested: bool
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    artifacts: list[GenerationArtifactOut] = Field(default_factory=list)


class GenerationCreated(BaseModel):
    job_id: uuid.UUID
    status: JobStatus


class CancelGenerationResponse(BaseModel):
    job_id: uuid.UUID
    status: JobStatus
    cancel_requested: bool


class MemoryProfilePatch(BaseModel):
    preferred_language: str | None = None
    tone: str | None = None
    difficulty: str | None = None
    image_style: str | None = None
    audience_notes: str | None = None
    banned_terms: list[str] | None = None
    preferred_task_types: list[str] | None = None
    tts_preferences: dict[str, Any] | None = None


class MemoryProfileOut(BaseModel):
    user_id: uuid.UUID
    explicit_profile: dict[str, Any]
    style_profile: dict[str, Any]
    recent_feedback: list[dict[str, Any]]


class FeedbackCreate(BaseModel):
    job_id: uuid.UUID | None = None
    rating: int = Field(ge=1, le=5)
    accepted: bool = False
    notes: str | None = None
    artifact_type: str | None = None
