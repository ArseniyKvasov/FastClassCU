import uuid
from dataclasses import dataclass

from fastapi import Header, HTTPException

from app.security import InvalidTokenError, verify_token
from fastclass_shared.context import bind_actor


@dataclass
class CurrentAdmin:
    user_id: uuid.UUID
    token: str
    role: str


async def get_current_admin(authorization: str | None = Header(default=None)) -> CurrentAdmin:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "missing_token"})

    token = authorization.removeprefix("Bearer ")
    try:
        claims = verify_token(token)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"})

    role = str(claims.get("role") or "")
    if role != "admin":
        raise HTTPException(status_code=403, detail={"code": "admin_only"})

    admin = CurrentAdmin(user_id=uuid.UUID(claims["sub"]), token=token, role=role)
    bind_actor(user_id=str(admin.user_id))
    return admin
