import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models import ContextType


class SubmitAnswerRequest(BaseModel):
    task_id: uuid.UUID
    context_type: ContextType
    context_id: uuid.UUID
    payload: dict


class AnswerOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    context_type: ContextType
    context_id: uuid.UUID
    task_type: str
    payload: dict
    correct_count: int
    wrong_count: int
    total_count: int
    auto_score: float | None
    manual_score: float | None
    is_checked: bool
    answered_at: datetime | None

    model_config = {"from_attributes": True}


class ManualScoreUpdate(BaseModel):
    score: float
