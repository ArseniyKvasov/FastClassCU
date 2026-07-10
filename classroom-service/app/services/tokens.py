import time
import uuid

import jwt

from app.config import settings


def mint_livekit_token(
    *, identity: uuid.UUID, room_name: str, is_teacher: bool, display_name: str
) -> str:
    """LiveKit access tokens are plain JWTs signed HS256 with the API secret -
    no SDK dependency needed, just the claim shape LiveKit expects."""
    now = int(time.time())
    grants: dict = {
        "room": room_name,
        "roomJoin": True,
        "canPublish": True,
        "canSubscribe": True,
        "canPublishData": is_teacher,
    }
    if is_teacher:
        grants["roomAdmin"] = True

    claims = {
        "iss": settings.livekit_api_key,
        "sub": str(identity),
        "name": display_name,
        "iat": now,
        "nbf": now,
        "exp": now + settings.livekit_token_ttl_seconds,
        "video": grants,
    }
    return jwt.encode(claims, settings.livekit_api_secret, algorithm="HS256")


def mint_whiteboard_token(
    *, board_id: str, user_id: uuid.UUID, username: str, is_teacher: bool
) -> str:
    """Separate secret from LiveKit's and from Auth Service's RS256 keys on
    purpose - if the whiteboard microservice's secret ever leaks, blast
    radius is limited to boards, not the rest of the system."""
    now = int(time.time())
    claims = {
        "board_id": board_id,
        "user_id": str(user_id),
        "username": username,
        "role": "moderator" if is_teacher else "editor",
        "iat": now,
        "exp": now + 300,  # short-lived by design - re-minted per session
    }
    return jwt.encode(claims, settings.whiteboard_jwt_secret, algorithm="HS256")
