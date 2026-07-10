import uuid
from datetime import datetime, timezone

from app.services.memory import derive_style_profile
from app.schemas import LessonBundleOut


def _lesson(title: str, task_types: list[str]) -> LessonBundleOut:
    return LessonBundleOut.model_validate(
        {
            "id": str(uuid.uuid4()),
            "owner_id": str(uuid.uuid4()),
            "title": title,
            "description": "desc",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sections": [
                {
                    "title": "Section",
                    "position": 0,
                    "tasks": [
                        {"task_type": task_type, "payload": {"content": "x"}, "position": index}
                        for index, task_type in enumerate(task_types)
                    ],
                }
            ],
        }
    )


def test_derive_style_profile_prefers_explicit_values():
    profile = derive_style_profile(
        lessons=[_lesson("Short title", ["text", "writing_task"]), _lesson("Another lesson", ["text"])],
        explicit_profile={"tone": "friendly", "difficulty": "b1", "preferred_language": "en"},
    )
    assert profile["tone"] == "friendly"
    assert profile["difficulty"] == "b1"
    assert profile["language"] == "en"
    assert profile["top_task_types"][0] == "text"
