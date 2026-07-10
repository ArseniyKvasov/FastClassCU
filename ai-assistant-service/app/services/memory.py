import uuid
from collections import Counter
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MemoryItem, MemoryKind, StyleProfile
from app.schemas import FeedbackCreate, LessonBundleOut, MemoryProfilePatch


def _compact_text(value: str | None) -> str:
    return (value or "").strip()


async def get_explicit_profile(db: AsyncSession, *, user_id: uuid.UUID) -> dict[str, Any]:
    row = await db.scalar(
        select(MemoryItem).where(
            MemoryItem.user_id == user_id,
            MemoryItem.kind == MemoryKind.profile,
            MemoryItem.scope == "explicit",
        )
    )
    return dict(row.content) if row else {}


async def patch_explicit_profile(
    db: AsyncSession, *, user_id: uuid.UUID, patch: MemoryProfilePatch
) -> dict[str, Any]:
    existing = await get_explicit_profile(db, user_id=user_id)
    updates = patch.model_dump(exclude_none=True)
    merged = {**existing, **updates}

    await db.execute(
        delete(MemoryItem).where(
            MemoryItem.user_id == user_id,
            MemoryItem.kind == MemoryKind.profile,
            MemoryItem.scope == "explicit",
        )
    )
    db.add(
        MemoryItem(
            user_id=user_id,
            kind=MemoryKind.profile,
            scope="explicit",
            content=merged,
        )
    )
    await db.flush()
    return merged


async def record_feedback(db: AsyncSession, *, user_id: uuid.UUID, feedback: FeedbackCreate) -> None:
    db.add(
        MemoryItem(
            user_id=user_id,
            kind=MemoryKind.feedback,
            scope="generation",
            weight=1.0 if feedback.accepted else 0.6,
            content=feedback.model_dump(mode="json"),
        )
    )
    await db.flush()


async def list_recent_feedback(
    db: AsyncSession, *, user_id: uuid.UUID, limit: int
) -> list[dict[str, Any]]:
    rows = (
        await db.scalars(
            select(MemoryItem)
            .where(MemoryItem.user_id == user_id, MemoryItem.kind == MemoryKind.feedback)
            .order_by(MemoryItem.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [dict(row.content) for row in rows]


def derive_style_profile(*, lessons: list[LessonBundleOut], explicit_profile: dict[str, Any]) -> dict[str, Any]:
    task_counts: Counter[str] = Counter()
    section_titles: list[str] = []
    title_lengths: list[int] = []
    descriptions: list[str] = []

    for lesson in lessons:
        title_lengths.append(len(lesson.title.split()))
        descriptions.append(_compact_text(lesson.description))
        for section in lesson.sections:
            section_titles.append(_compact_text(section.title))
            for task in section.tasks:
                task_counts[task.task_type] += 1

    top_task_types = [task_type for task_type, _count in task_counts.most_common(5)]
    avg_title_words = round(sum(title_lengths) / len(title_lengths), 2) if title_lengths else 0.0
    density = "dense" if sum(task_counts.values()) >= max(len(lessons), 1) * 6 else "balanced"

    tone = explicit_profile.get("tone") or "clear"
    difficulty = explicit_profile.get("difficulty") or "mixed"
    language = explicit_profile.get("preferred_language") or "ru"

    return {
        "language": language,
        "tone": tone,
        "difficulty": difficulty,
        "top_task_types": top_task_types,
        "average_title_words": avg_title_words,
        "section_title_examples": [title for title in section_titles if title][:4],
        "content_density": density,
        "has_media_bias": any(task in {"image", "audio", "file"} for task in top_task_types),
        "description_examples": [text for text in descriptions if text][:2],
    }


async def upsert_style_profile(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    lessons: list[LessonBundleOut],
    explicit_profile: dict[str, Any],
) -> dict[str, Any]:
    profile = derive_style_profile(lessons=lessons, explicit_profile=explicit_profile)
    row = await db.get(StyleProfile, user_id)
    lesson_ids = [str(lesson.id) for lesson in lessons]
    if row is None:
        row = StyleProfile(user_id=user_id, profile=profile, source_lesson_ids=lesson_ids)
        db.add(row)
    else:
        row.profile = profile
        row.source_lesson_ids = lesson_ids
    await db.flush()
    return profile


async def get_style_profile(db: AsyncSession, *, user_id: uuid.UUID) -> dict[str, Any]:
    row = await db.get(StyleProfile, user_id)
    return dict(row.profile) if row else {}
