import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models import DerivationType, ProcessingStatus


class LessonCreate(BaseModel):
    owner_id: uuid.UUID
    title: str
    description: str | None = None


class LessonOut(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    origin_lesson_id: uuid.UUID | None
    derivation_type: DerivationType
    title: str
    description: str | None
    is_public: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LessonListItemOut(LessonOut):
    task_count: int = 0


class DeriveLessonRequest(BaseModel):
    owner_id: uuid.UUID


class SyncReport(BaseModel):
    synced_lesson_id: uuid.UUID
    overwritten_edited: list[uuid.UUID]


class SectionCreate(BaseModel):
    title: str = ""


class SectionOut(BaseModel):
    id: uuid.UUID
    lesson_id: uuid.UUID
    title: str
    position: int

    model_config = {"from_attributes": True}


class TaskCreateRequest(BaseModel):
    task_type: str
    payload: dict
    created_by: uuid.UUID
    file_id: uuid.UUID | None = None


class TaskUpdateRequest(BaseModel):
    payload: dict
    edited_by: uuid.UUID
    file_id: uuid.UUID | None = None


class TaskOut(BaseModel):
    id: uuid.UUID
    section_id: uuid.UUID
    task_type: str
    current_content_id: uuid.UUID
    position: int

    model_config = {"from_attributes": True}


class TaskWithContentOut(TaskOut):
    payload: dict


class FileAssetOut(BaseModel):
    id: uuid.UUID
    sha256: str
    size_bytes: int
    mime_type: str | None
    original_filename: str | None
    processing_status: ProcessingStatus

    model_config = {"from_attributes": True}


class LessonBundleFileRef(BaseModel):
    id: uuid.UUID
    mime_type: str | None = None
    original_filename: str | None = None


class LessonBundleTask(BaseModel):
    task_type: str
    payload: dict
    file_id: uuid.UUID | None = None
    position: int = 0
    file: LessonBundleFileRef | None = None


class LessonBundleSection(BaseModel):
    title: str = ""
    position: int = 0
    tasks: list[LessonBundleTask] = []


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


class QuotaOut(BaseModel):
    teacher_id: uuid.UUID
    storage_bytes: int
    limit_bytes: int


class GcReport(BaseModel):
    reclaimed_contents: int
    reclaimed_files: int


class CollectionCreate(BaseModel):
    owner_id: uuid.UUID
    title: str
    description: str | None = None
    is_sequential: bool = False


class CollectionOut(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    title: str
    description: str | None
    is_sequential: bool

    model_config = {"from_attributes": True}


class CollectionItemCreate(BaseModel):
    lesson_id: uuid.UUID
    sequence_order: int = 0


class QualityFeedbackCreate(BaseModel):
    user_id: uuid.UUID
    rating: int
    comment: str | None = None


class QualityFeedbackOut(BaseModel):
    id: uuid.UUID
    lesson_id: uuid.UUID
    user_id: uuid.UUID
    rating: int
    comment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
