import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models import SessionStatus, TargetType


class AssignmentTaskIn(BaseModel):
    task_id: uuid.UUID
    weight: int | None = None


class AssignmentCreate(BaseModel):
    title: str
    lesson_id: uuid.UUID
    deadline: datetime | None = None
    time_limit_minutes: int | None = None
    attempts_limit: int = Field(default=1, ge=1)
    show_results_immediately: bool = True
    target_type: TargetType
    target_classroom_id: uuid.UUID | None = None
    tasks: list[AssignmentTaskIn] = Field(default_factory=list)


class AssignmentUpdate(BaseModel):
    title: str | None = None
    deadline: datetime | None = None
    time_limit_minutes: int | None = None
    attempts_limit: int | None = Field(default=None, ge=1)
    show_results_immediately: bool | None = None
    tasks: list[AssignmentTaskIn] | None = None


class AssignmentTaskOut(BaseModel):
    task_id: uuid.UUID
    position: int
    weight: int | None

    model_config = {"from_attributes": True}


class AssignmentOut(BaseModel):
    id: uuid.UUID
    teacher_id: uuid.UUID
    lesson_id: uuid.UUID
    title: str
    deadline: datetime | None
    time_limit_minutes: int | None
    attempts_limit: int
    show_results_immediately: bool
    target_type: TargetType
    target_classroom_id: uuid.UUID | None
    created_at: datetime
    tasks: list[AssignmentTaskOut] = []

    model_config = {"from_attributes": True}


class SessionOut(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    attempt_number: int
    status: SessionStatus
    started_at: datetime
    submitted_at: datetime | None
    grade: float | None
    teacher_comment: str
    time_left_seconds: int | None = None

    model_config = {"from_attributes": True}


class SessionCommentUpdate(BaseModel):
    comment: str


class SessionStatusUpdate(BaseModel):
    status: SessionStatus


class SessionGradeOverride(BaseModel):
    grade: float = Field(ge=0, le=100)
