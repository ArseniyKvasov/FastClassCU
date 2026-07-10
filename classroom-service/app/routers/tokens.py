from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.deps import CurrentUser, get_current_user, require_member, require_teacher
from app.models import Classroom, ClassroomSettings, Membership
from app.services import tokens as tokens_svc
from app.services import whiteboard_api
from app.services.whiteboard_api import WhiteboardServiceError

router = APIRouter(prefix="/classrooms", tags=["tokens"])


async def _display_name(db: AsyncSession, classroom: Classroom, user: CurrentUser) -> str:
    if user.user_id == classroom.teacher_id:
        return "Teacher"
    member = await db.scalar(
        select(Membership).where(
            Membership.classroom_id == classroom.id, Membership.user_id == user.user_id
        )
    )
    return member.display_name if member else "Student"


@router.get("/{classroom_id}/video-token")
async def get_video_token(
    classroom: Classroom = Depends(require_member),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    classroom_settings = await db.get(ClassroomSettings, classroom.id)
    if classroom_settings is None or not classroom_settings.communication_enabled:
        raise HTTPException(status_code=403, detail={"code": "communication_disabled"})

    is_teacher = user.user_id == classroom.teacher_id
    display_name = await _display_name(db, classroom, user)
    token = tokens_svc.mint_livekit_token(
        identity=user.user_id,
        room_name=f"classroom-{classroom.id}",
        is_teacher=is_teacher,
        display_name=display_name,
    )
    return {"token": token, "ws_url": settings.livekit_ws_url}


@router.get("/{classroom_id}/whiteboard-token")
async def get_whiteboard_token(
    classroom: Classroom = Depends(require_member),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    classroom_settings = await db.get(ClassroomSettings, classroom.id)
    if classroom_settings is None or not classroom_settings.whiteboard_enabled:
        raise HTTPException(status_code=403, detail={"code": "whiteboard_disabled"})

    is_teacher = user.user_id == classroom.teacher_id
    display_name = await _display_name(db, classroom, user)
    token = tokens_svc.mint_whiteboard_token(
        board_id=str(classroom.id),
        user_id=user.user_id,
        username=display_name,
        is_teacher=is_teacher,
    )
    return {"token": token, "board_id": str(classroom.id)}


@router.post("/{classroom_id}/whiteboard/access")
async def update_whiteboard_access(
    allow_students_draw: bool,
    classroom: Classroom = Depends(require_teacher),
):
    try:
        return await whiteboard_api.update_board_drawing_access(
            str(classroom.id), allow_students_draw
        )
    except WhiteboardServiceError as exc:
        raise HTTPException(status_code=502, detail={"code": "whiteboard_service_error", "message": str(exc)})
