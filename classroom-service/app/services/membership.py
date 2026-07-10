import uuid

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Classroom, ClassroomSettings, Membership, MembershipRole
from app.passwords import generate_join_password, hash_password, verify_password
from app.services import presence
from app.services.events import emit_event
from app.services.rate_limit import check_join_lockout, record_join_attempt


class InvalidJoinPasswordError(Exception):
    pass


async def join_classroom(
    db: AsyncSession,
    r: redis.Redis,
    *,
    classroom_id: uuid.UUID,
    user_id: uuid.UUID,
    client_ip: str,
    password: str,
    display_name: str,
) -> Membership:
    # Rate limiting happens before touching the password at all - every
    # attempt counts against the budget whether it turns out right or wrong.
    await check_join_lockout(r, classroom_id=classroom_id)
    await record_join_attempt(r, classroom_id=classroom_id, client_ip=client_ip)

    classroom_settings = await db.get(ClassroomSettings, classroom_id)
    if classroom_settings is None or not verify_password(
        password, classroom_settings.join_password_hash
    ):
        raise InvalidJoinPasswordError()

    existing = await db.scalar(
        select(Membership).where(
            Membership.classroom_id == classroom_id, Membership.user_id == user_id
        )
    )
    if existing is not None:
        return existing

    member = Membership(
        classroom_id=classroom_id,
        user_id=user_id,
        display_name=display_name,
        role=MembershipRole.student,
    )
    db.add(member)
    await db.flush()

    await emit_event(
        db,
        event_type="student_joined",
        payload={"classroom_id": str(classroom_id), "user_id": str(user_id)},
    )
    return member


async def leave_classroom(db: AsyncSession, *, classroom_id: uuid.UUID, user_id: uuid.UUID) -> None:
    member = await db.scalar(
        select(Membership).where(
            Membership.classroom_id == classroom_id, Membership.user_id == user_id
        )
    )
    if member is None:
        return
    await db.delete(member)
    await db.flush()
    await emit_event(
        db,
        event_type="student_left",
        payload={"classroom_id": str(classroom_id), "user_id": str(user_id)},
    )


async def remove_student(
    db: AsyncSession, *, classroom_id: uuid.UUID, student_user_id: uuid.UUID
) -> None:
    await leave_classroom(db, classroom_id=classroom_id, user_id=student_user_id)


async def get_roster(
    db: AsyncSession, r: redis.Redis, *, classroom_id: uuid.UUID
) -> tuple[list[Membership], list[uuid.UUID]]:
    members = (
        await db.scalars(select(Membership).where(Membership.classroom_id == classroom_id))
    ).all()
    online_ids = await presence.list_online(r, classroom_id=classroom_id)
    return list(members), online_ids


async def apply_user_upgraded(
    db: AsyncSession, *, old_user_id: uuid.UUID, new_user_id: uuid.UUID
) -> int:
    """Consumes Auth Service's 'user_upgraded' event: a guest who joined a
    classroom before creating a full account gets a NEW user_id from Auth
    Service on upgrade (different from their old GuestSession.id) - this
    repoints their Membership rows so they don't lose classroom access.

    If the upgraded account already happens to have its own membership in
    some classroom (e.g. they joined once as a guest, then again after
    logging in properly), the guest row is dropped instead of repointed -
    the real membership wins, and we don't violate the (classroom_id,
    user_id) uniqueness constraint."""
    rows = (
        await db.scalars(select(Membership).where(Membership.user_id == old_user_id))
    ).all()
    updated = 0
    for row in rows:
        conflict = await db.scalar(
            select(Membership).where(
                Membership.classroom_id == row.classroom_id,
                Membership.user_id == new_user_id,
            )
        )
        if conflict is not None:
            await db.delete(row)
        else:
            row.user_id = new_user_id
            updated += 1
    await db.flush()
    return updated


async def rotate_join_password(db: AsyncSession, *, classroom: Classroom) -> str:
    classroom_settings = await db.get(ClassroomSettings, classroom.id)
    plaintext = generate_join_password()
    classroom_settings.join_password_hash = hash_password(plaintext)
    from datetime import datetime, timezone

    classroom_settings.join_password_set_at = datetime.now(timezone.utc)
    await db.flush()
    return plaintext
