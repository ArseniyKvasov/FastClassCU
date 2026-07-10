from pathlib import Path

import jwt

from app.config import settings


class InvalidTokenError(Exception):
    pass


def _public_key() -> str:
    return Path(settings.jwt_public_key_path).read_text()


def verify_token(token: str) -> dict:
    try:
        return jwt.decode(
            token, _public_key(), algorithms=["RS256"], issuer=settings.jwt_issuer
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
