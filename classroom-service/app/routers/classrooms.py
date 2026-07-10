import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import CurrentUser, get_current_user, require_member, require_teacher
from app.models import Classroom
from app.schemas import (
    ClassroomCreate,
    ClassroomCreatedOut,
    ClassroomOut,
    ClassroomUpdate,
    SettingsOut,
    SettingsUpdate,
)
from app.services import classrooms as classrooms_svc

router = APIRouter(prefix="/classrooms", tags=["classrooms"])


@router.post("", response_model=ClassroomCreatedOut)
async def create_classroom(
    body: ClassroomCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    classroom, plaintext = await classrooms_svc.create_classroom(
        db, teacher_id=user.user_id, title=body.title, lesson_id=body.lesson_id
    )
    await db.commit()
    return {**ClassroomOut.model_validate(classroom).model_dump(), "join_password": plaintext}


@router.get("", response_model=list[ClassroomOut])
async def list_classrooms(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
) -> list[Classroom]:
    return await classrooms_svc.list_classrooms_for_user(db, user_id=user.user_id)


@router.get("/{classroom_id}", response_model=ClassroomOut)
async def get_classroom(classroom: Classroom = Depends(require_member)) -> Classroom:
    return classroom


@router.patch("/{classroom_id}", response_model=ClassroomOut)
async def update_classroom(
    body: ClassroomUpdate,
    classroom: Classroom = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> Classroom:
    return await classrooms_svc.update_classroom(
        db, classroom=classroom, title=body.title, lesson_id=body.lesson_id
    )


@router.delete("/{classroom_id}", status_code=204)
async def delete_classroom(
    classroom: Classroom = Depends(require_teacher), db: AsyncSession = Depends(get_db)
) -> None:
    await classrooms_svc.delete_classroom(db, classroom=classroom)
    await db.commit()


@router.get("/{classroom_id}/settings", response_model=SettingsOut)
async def get_settings(
    classroom_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _classroom: Classroom = Depends(require_member),
):
    result = await classrooms_svc.get_settings(db, classroom_id=classroom_id)
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "classroom_not_found"})
    return result


@router.patch("/{classroom_id}/settings", response_model=SettingsOut)
async def update_settings(
    classroom_id: uuid.UUID,
    body: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _classroom: Classroom = Depends(require_teacher),
):
    classroom_settings = await classrooms_svc.get_settings(db, classroom_id=classroom_id)
    if classroom_settings is None:
        raise HTTPException(status_code=404, detail={"code": "classroom_not_found"})
    updated = await classrooms_svc.update_settings(
        db,
        classroom_settings=classroom_settings,
        communication_enabled=body.communication_enabled,
        whiteboard_enabled=body.whiteboard_enabled,
        copying_enabled=body.copying_enabled,
    )
    await db.commit()
    return updated
