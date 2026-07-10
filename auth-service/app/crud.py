import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GuestSession, RefreshToken, User
from app.services.events import emit_event


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_raw_token() -> str:
    return secrets.token_urlsafe(48)


async def create_guest_session(db: AsyncSession, ttl_seconds: int) -> GuestSession:
    session = GuestSession(
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    )
    db.add(session)
    await db.flush()
    await emit_event(
        db,
        event_type="guest_created",
        payload={"guest_session_id": str(session.id)},
    )
    await db.commit()
    await db.refresh(session)
    return session


async def get_or_create_user(
    db: AsyncSession,
    provider: str,
    provider_user_id: str,
    email: str | None,
    display_name: str | None,
) -> User:
    result = await db.execute(
        select(User).where(
            User.provider == provider, User.provider_user_id == provider_user_id
        )
    )
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(
        provider=provider,
        provider_user_id=provider_user_id,
        email=email,
        display_name=display_name,
    )
    db.add(user)
    await db.flush()
    await emit_event(
        db,
        event_type="user_created",
        payload={"user_id": str(user.id), "provider": provider},
    )
    await db.commit()
    await db.refresh(user)
    return user


async def issue_refresh_token(db: AsyncSession, user_id: uuid.UUID, ttl_seconds: int) -> str:
    raw = new_raw_token()
    token = RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
    )
    db.add(token)
    await db.commit()
    return raw


async def consume_refresh_token(db: AsyncSession, raw: str) -> RefreshToken | None:
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == _hash_token(raw))
    )
    token = result.scalar_one_or_none()
    if not token or token.revoked or token.expires_at < datetime.now(timezone.utc):
        return None
    return token


async def revoke_refresh_token(db: AsyncSession, raw: str) -> None:
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == _hash_token(raw))
    )
    token = result.scalar_one_or_none()
    if token:
        token.revoked = True
        await db.commit()


async def upgrade_guest_to_full(db: AsyncSession, guest_session_id: str, user_id: uuid.UUID) -> None:
    result = await db.execute(
        select(GuestSession).where(GuestSession.id == guest_session_id)
    )
    session = result.scalar_one_or_none()
    if session:
        session.upgraded_to_user_id = user_id
        # Same transaction as the flag flip, not after - any service that
        # keyed data to the guest session id (e.g. Classroom Service's
        # Membership.user_id) subscribes to this to repoint it.
        await emit_event(
            db,
            event_type="user_upgraded",
            payload={"old_guest_session_id": str(guest_session_id), "new_user_id": str(user_id)},
        )
        await db.commit()
