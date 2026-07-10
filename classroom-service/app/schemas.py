import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models import MembershipRole


class ClassroomCreate(BaseModel):
    title: str
    lesson_id: uuid.UUID | None = None


class ClassroomUpdate(BaseModel):
    title: str | None = None
    lesson_id: uuid.UUID | None = None


class ClassroomOut(BaseModel):
    id: uuid.UUID
    teacher_id: uuid.UUID
    title: str
    lesson_id: uuid.UUID | None
    is_preview: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ClassroomCreatedOut(ClassroomOut):
    join_password: str


class SettingsUpdate(BaseModel):
    communication_enabled: bool | None = None
    whiteboard_enabled: bool | None = None
    copying_enabled: bool | None = None


class SettingsOut(BaseModel):
    communication_enabled: bool
    whiteboard_enabled: bool
    copying_enabled: bool
    join_password_set_at: datetime

    model_config = {"from_attributes": True}


class JoinRequest(BaseModel):
    password: str
    display_name: str = Field(min_length=1, max_length=255)


class MembershipOut(BaseModel):
    id: uuid.UUID
    classroom_id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    role: MembershipRole
    joined_at: datetime

    model_config = {"from_attributes": True}


class RosterOut(BaseModel):
    members: list[MembershipOut]
    online_user_ids: list[uuid.UUID]


class RotatePasswordOut(BaseModel):
    join_password: str


class UserUpgradedEvent(BaseModel):
    old_user_id: uuid.UUID
    new_user_id: uuid.UUID


class ChatSend(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    classroom_id: uuid.UUID
    sender_id: uuid.UUID
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}
