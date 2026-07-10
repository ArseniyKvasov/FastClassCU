import uuid
from dataclasses import dataclass

from fastapi import Header, HTTPException

from fastclass_shared.context import bind_actor
from app.security import InvalidTokenError, verify_token


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
