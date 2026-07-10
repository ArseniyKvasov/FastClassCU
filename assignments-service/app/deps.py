import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Assignment
from app.security import InvalidTokenError, verify_token
from fastclass_shared.context import bind_actor


@dataclass
class CurrentUser:
    user_id: uuid.UUID
    access_level: str
    token: str


async def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "missing_token"})

    token = authorization.removeprefix("Bearer ")
    try:
        claims = verify_token(token)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"})

    user = CurrentUser(
        user_id=uuid.UUID(claims["sub"]), access_level=claims["access_level"], token=token
    )
    bind_actor(user_id=str(user.user_id))
    return user


async def require_assignment_teacher(
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Assignment:
    assignment = await db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail={"code": "assignment_not_found"})
    if assignment.teacher_id != user.user_id:
        raise HTTPException(status_code=403, detail={"code": "teacher_only"})
    return assignment


async def get_assignment_or_404(
    assignment_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Assignment:
    assignment = await db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail={"code": "assignment_not_found"})
    return assignment
