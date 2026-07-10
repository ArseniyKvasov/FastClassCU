import uuid
from dataclasses import dataclass

from fastapi import Cookie, HTTPException

from app.config import settings
from app.security import InvalidTokenError, verify_token


@dataclass
class CurrentSession:
    user_id: uuid.UUID
    access_level: str
    access_token: str


def _decode_cookie(access_token: str | None) -> CurrentSession | None:
    if not access_token:
        return None
    try:
        claims = verify_token(access_token)
    except InvalidTokenError:
        return None
    return CurrentSession(
        user_id=uuid.UUID(claims["sub"]),
        access_level=claims["access_level"],
        access_token=access_token,
    )


async def get_optional_session(
    fc_session: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> CurrentSession | None:
    return _decode_cookie(fc_session)


async def get_current_session(
    fc_session: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> CurrentSession:
    session = _decode_cookie(fc_session)
    if session is None:
        raise HTTPException(status_code=401, detail={"code": "not_authenticated"})
    return session
