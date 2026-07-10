from pathlib import Path

import jwt

from app.config import settings


class InvalidTokenError(Exception):
    pass


def _read_public_key(path: str) -> str:
    return Path(path).read_text()


def verify_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            _read_public_key(settings.jwt_public_key_path),
            algorithms=["RS256"],
            issuer=settings.jwt_issuer,
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
