from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.schemas import UserUpgradedEvent
from app.services import membership as membership_svc
from fastclass_shared.auth import ServiceAuthError, authenticate_service_request

router = APIRouter(prefix="/internal", tags=["internal"])


def require_classroom_user_upgraded_write(
    authorization: str | None = Header(default=None),
    x_service_token: str | None = Header(default=None),
) -> None:
    try:
        authenticate_service_request(
            authorization=authorization,
            x_service_token=x_service_token,
            public_key_path=settings.jwt_public_key_path,
            issuer=settings.jwt_issuer,
            required_scopes={"classroom:user-upgraded:write"},
            allow_legacy_token=settings.allow_legacy_internal_service_token,
            legacy_token=settings.internal_service_token,
        )
    except ServiceAuthError:
        raise HTTPException(status_code=401, detail={"code": "invalid_service_token"})


@router.post("/events/user-upgraded")
async def user_upgraded(
    body: UserUpgradedEvent,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(require_classroom_user_upgraded_write),
) -> dict:
    updated = await membership_svc.apply_user_upgraded(
        db, old_user_id=body.old_user_id, new_user_id=body.new_user_id
    )
    await db.commit()
    return {"memberships_updated": updated}
