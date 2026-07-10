import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.schemas import LessonBundleOut
from app.services import content_client, memory


async def build_context_pack(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    source_lesson: LessonBundleOut | None = None,
    request_payload: dict[str, Any],
) -> dict[str, Any]:
    explicit_profile = await memory.get_explicit_profile(db, user_id=user_id)
    recent_lessons = await content_client.list_owner_lessons(
        user_id, limit=settings.recent_lessons_limit
    )
    style_profile = await memory.upsert_style_profile(
        db,
        user_id=user_id,
        lessons=recent_lessons,
        explicit_profile=explicit_profile,
    )
    task_registry = await content_client.get_task_registry()
    feedback = await memory.list_recent_feedback(
        db, user_id=user_id, limit=settings.max_feedback_items
    )

    lesson_examples = [
        {
            "id": str(lesson.id),
            "title": lesson.title,
            "description": lesson.description,
            "sections": [
                {
                    "title": section.title,
                    "task_types": [task.task_type for task in section.tasks],
                }
                for section in lesson.sections
            ],
        }
        for lesson in recent_lessons[: settings.max_context_lessons]
    ]

    return {
        "user_id": str(user_id),
        "request": request_payload,
        "explicit_profile": explicit_profile,
        "style_profile": style_profile,
        "recent_lessons": lesson_examples,
        "recent_feedback": feedback,
        "task_registry": [item.model_dump(mode="json") for item in task_registry.tasks],
        "source_lesson": source_lesson.model_dump(mode="json") if source_lesson else None,
        "context_version": 1,
    }
