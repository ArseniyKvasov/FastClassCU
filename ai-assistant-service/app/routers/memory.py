from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import CurrentUser, get_current_user
from app.schemas import FeedbackCreate, MemoryProfileOut, MemoryProfilePatch
from app.services import content_client, memory

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/profile", response_model=MemoryProfileOut)
async def get_memory_profile(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> MemoryProfileOut:
    explicit_profile = await memory.get_explicit_profile(db, user_id=user.user_id)
    recent_lessons = await content_client.list_owner_lessons(user.user_id, limit=6)
    style_profile = await memory.upsert_style_profile(
        db,
        user_id=user.user_id,
        lessons=recent_lessons,
        explicit_profile=explicit_profile,
    )
    feedback = await memory.list_recent_feedback(db, user_id=user.user_id, limit=10)
    await db.commit()
    return MemoryProfileOut(
        user_id=user.user_id,
        explicit_profile=explicit_profile,
        style_profile=style_profile,
        recent_feedback=feedback,
    )


@router.patch("/profile", response_model=MemoryProfileOut)
async def patch_memory_profile(
    body: MemoryProfilePatch,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> MemoryProfileOut:
    explicit_profile = await memory.patch_explicit_profile(db, user_id=user.user_id, patch=body)
    recent_lessons = await content_client.list_owner_lessons(user.user_id, limit=6)
    style_profile = await memory.upsert_style_profile(
        db,
        user_id=user.user_id,
        lessons=recent_lessons,
        explicit_profile=explicit_profile,
    )
    feedback = await memory.list_recent_feedback(db, user_id=user.user_id, limit=10)
    await db.commit()
    return MemoryProfileOut(
        user_id=user.user_id,
        explicit_profile=explicit_profile,
        style_profile=style_profile,
        recent_feedback=feedback,
    )


@router.post("/feedback", status_code=204)
async def create_feedback(
    body: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    await memory.record_feedback(db, user_id=user.user_id, feedback=body)
    await db.commit()
