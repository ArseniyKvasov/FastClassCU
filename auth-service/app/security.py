import time
import uuid
from pathlib import Path

import jwt

from app.config import settings


def _read_key(path: str) -> str:
    return Path(path).read_text()


def mint_token(
    *,
    subject: str,
    access_level: str,
    role: str | None = None,
    ttl_seconds: int,
    extra_claims: dict | None = None,
) -> str:
    now = int(time.time())
    claims = {
        "sub": subject,
        "iss": settings.jwt_issuer,
        "access_level": access_level,
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": str(uuid.uuid4()),
    }
    if role is not None:
        claims["role"] = role
    if extra_claims:
        claims.update(extra_claims)

    private_key = _read_key(settings.jwt_private_key_path)
    return jwt.encode(claims, private_key, algorithm="RS256")


def verify_token(token: str) -> dict:
    public_key = _read_key(settings.jwt_public_key_path)
    return jwt.decode(token, public_key, algorithms=["RS256"], issuer=settings.jwt_issuer)


def public_key_pem() -> str:
    return _read_key(settings.jwt_public_key_path)
