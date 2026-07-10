import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastclass_shared.context import bind_actor
from app.db import get_db
from app.models import Classroom, Membership
from app.security import InvalidTokenError, verify_token


@dataclass
class CurrentUser:
    user_id: uuid.UUID
    access_level: str  # "guest" | "full"


async def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "missing_token"})

    token = authorization.removeprefix("Bearer ")
    try:
        claims = verify_token(token)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"})

    user = CurrentUser(user_id=uuid.UUID(claims["sub"]), access_level=claims["access_level"])
    bind_actor(user_id=str(user.user_id))
    return user


async def require_teacher(
    classroom_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Classroom:
    classroom = await db.get(Classroom, classroom_id)
    if classroom is None:
        raise HTTPException(status_code=404, detail={"code": "classroom_not_found"})
    if classroom.teacher_id != user.user_id:
        raise HTTPException(status_code=403, detail={"code": "teacher_only"})
    return classroom


async def require_member(
    classroom_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Classroom:
    """The ONE place membership is checked - replaces the ~8 duplicated,
    inconsistent inline checks the old codebase had."""
    classroom = await db.get(Classroom, classroom_id)
    if classroom is None:
        raise HTTPException(status_code=404, detail={"code": "classroom_not_found"})
    if classroom.teacher_id == user.user_id:
        return classroom

    member = await db.scalar(
        select(Membership).where(
            Membership.classroom_id == classroom_id,
            Membership.user_id == user.user_id,
        )
    )
    if member is None:
        raise HTTPException(status_code=403, detail={"code": "not_a_member"})
    return classroom
