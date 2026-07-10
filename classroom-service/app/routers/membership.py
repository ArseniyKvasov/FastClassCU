import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import CurrentUser, get_current_user, require_member, require_teacher
from app.models import Classroom
from app.redis_client import get_redis
from app.schemas import JoinRequest, MembershipOut, RosterOut, RotatePasswordOut
from app.services import membership as membership_svc
from app.services.rate_limit import RateLimitExceeded
from fastclass_shared import get_client_ip

router = APIRouter(prefix="/classrooms", tags=["membership"])


@router.post("/{classroom_id}/join", response_model=MembershipOut)
async def join_classroom(
    classroom_id: uuid.UUID,
    body: JoinRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    r=Depends(get_redis),
):
    try:
        member = await membership_svc.join_classroom(
            db,
            r,
            classroom_id=classroom_id,
            user_id=user.user_id,
            client_ip=get_client_ip(request),
            password=body.password,
            display_name=body.display_name,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={"code": "too_many_attempts", "retry_after_seconds": exc.retry_after_seconds},
        )
    except membership_svc.InvalidJoinPasswordError:
        raise HTTPException(status_code=403, detail={"code": "invalid_password"})

    await db.commit()
    return member


@router.post("/{classroom_id}/leave", status_code=204)
async def leave_classroom(
    classroom_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    await membership_svc.leave_classroom(db, classroom_id=classroom_id, user_id=user.user_id)
    await db.commit()


@router.delete("/{classroom_id}/students/{student_user_id}", status_code=204)
async def remove_student(
    classroom_id: uuid.UUID,
    student_user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _classroom: Classroom = Depends(require_teacher),
) -> None:
    await membership_svc.remove_student(
        db, classroom_id=classroom_id, student_user_id=student_user_id
    )
    await db.commit()


@router.get("/{classroom_id}/roster", response_model=RosterOut)
async def get_roster(
    classroom_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    r=Depends(get_redis),
    _classroom: Classroom = Depends(require_member),
):
    members, online_ids = await membership_svc.get_roster(db, r, classroom_id=classroom_id)
    return {"members": members, "online_user_ids": online_ids}


@router.post("/{classroom_id}/rotate-password", response_model=RotatePasswordOut)
async def rotate_password(
    classroom: Classroom = Depends(require_teacher), db: AsyncSession = Depends(get_db)
):
    plaintext = await membership_svc.rotate_join_password(db, classroom=classroom)
    await db.commit()
    return {"join_password": plaintext}
