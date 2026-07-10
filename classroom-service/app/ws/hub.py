import asyncio
import json
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.deps import CurrentUser
from app.models import ChatMessage, Classroom, ClassroomSettings, Membership
from app.redis_client import get_redis_client
from app.security import InvalidTokenError, verify_token
from app.services import presence
from app.ws import handlers
from app.ws.manager import channel_name

router = APIRouter()


async def _authenticate(token: str) -> CurrentUser | None:
    try:
        claims = verify_token(token)
    except InvalidTokenError:
        return None
    return CurrentUser(user_id=uuid.UUID(claims["sub"]), access_level=claims["access_level"])


async def _load_classroom_if_member(classroom_id: uuid.UUID, user_id: uuid.UUID) -> Classroom | None:
    async with SessionLocal() as db:
        classroom = await db.get(Classroom, classroom_id)
        if classroom is None:
            return None
        if classroom.teacher_id == user_id:
            return classroom
        member = await db.scalar(
            select(Membership).where(
                Membership.classroom_id == classroom_id, Membership.user_id == user_id
            )
        )
        return classroom if member else None


async def _build_snapshot(classroom: Classroom, r) -> dict:
    """Everything a freshly (re)connected client needs in ONE message - no
    cascade of follow-up REST calls to reconstruct state, and built entirely
    from durable/shared storage (Postgres + Redis), never from this worker's
    own memory - so any worker can answer a reconnect identically."""
    async with SessionLocal() as db:
        classroom_settings = await db.get(ClassroomSettings, classroom.id)
        members = (
            await db.scalars(select(Membership).where(Membership.classroom_id == classroom.id))
        ).all()
        recent_chat = (
            await db.scalars(
                select(ChatMessage)
                .where(ChatMessage.classroom_id == classroom.id)
                .order_by(ChatMessage.created_at.desc())
                .limit(30)
            )
        ).all()

    online_ids = await presence.list_online(r, classroom_id=classroom.id)
    observed = await r.get(f"classroom:{classroom.id}:observed_student")
    focus_raw = await r.get(f"classroom:{classroom.id}:focus")

    return {
        "type": "snapshot",
        "classroom": {
            "id": str(classroom.id),
            "title": classroom.title,
            "teacher_id": str(classroom.teacher_id),
        },
        "settings": {
            "communication_enabled": classroom_settings.communication_enabled,
            "whiteboard_enabled": classroom_settings.whiteboard_enabled,
            "copying_enabled": classroom_settings.copying_enabled,
        }
        if classroom_settings
        else None,
        "members": [
            {
                "user_id": str(m.user_id),
                "display_name": m.display_name,
                "role": m.role,
            }
            for m in members
        ],
        "online_user_ids": [str(uid) for uid in online_ids],
        "recent_chat": [
            {
                "id": str(c.id),
                "sender_id": str(c.sender_id),
                "body": c.body,
                "created_at": c.created_at.isoformat(),
            }
            for c in reversed(recent_chat)
        ],
        "observed_student_id": observed,
        "focus": json.loads(focus_raw) if focus_raw else None,
    }


@router.websocket("/ws/classrooms/{classroom_id}")
async def classroom_socket(websocket: WebSocket, classroom_id: uuid.UUID, token: str = Query(...)):
    user = await _authenticate(token)
    if user is None:
        await websocket.close(code=4401)
        return

    classroom = await _load_classroom_if_member(classroom_id, user.user_id)
    if classroom is None:
        await websocket.close(code=4403)
        return

    await websocket.accept()

    connection_id = str(uuid.uuid4())
    r = get_redis_client()

    await presence.mark_online(
        r, classroom_id=classroom_id, user_id=user.user_id, connection_id=connection_id
    )

    snapshot = await _build_snapshot(classroom, r)
    await websocket.send_json(snapshot)

    pubsub = r.pubsub()
    await pubsub.subscribe(channel_name(classroom_id))

    async def forward_pubsub_to_client() -> None:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            await websocket.send_text(message["data"])

    forward_task = asyncio.create_task(forward_pubsub_to_client())

    # ONE heartbeat mechanism: the client must send SOMETHING (a `ping`, or
    # any message) at least every ws_heartbeat_interval_seconds. If nothing
    # arrives for interval * missed_limit seconds, treat the connection as
    # dead. No separate server-push watchdog racing a client-push heartbeat
    # like the old system had - just a read timeout.
    idle_timeout = settings.ws_heartbeat_interval_seconds * settings.ws_heartbeat_missed_limit

    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=idle_timeout)
            except asyncio.TimeoutError:
                await websocket.close(code=4001)
                break

            try:
                incoming = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "code": "invalid_json"})
                continue

            response = await handlers.dispatch(
                session_factory=SessionLocal,
                r=r,
                classroom=classroom,
                user=user,
                connection_id=connection_id,
                message=incoming,
            )
            if response is not None:
                await websocket.send_json(response)
    except WebSocketDisconnect:
        pass
    finally:
        forward_task.cancel()
        await pubsub.unsubscribe(channel_name(classroom_id))
        await pubsub.aclose()
        await presence.mark_offline(
            r, classroom_id=classroom_id, user_id=user.user_id, connection_id=connection_id
        )
        await r.aclose()
