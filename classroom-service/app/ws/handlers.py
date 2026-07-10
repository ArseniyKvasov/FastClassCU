import uuid

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.deps import CurrentUser
from app.models import Classroom
from app.services import presence


async def dispatch(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    r: redis.Redis,
    classroom: Classroom,
    user: CurrentUser,
    connection_id: str,
    message: dict,
) -> dict | None:
    """One switch, one place messages are routed - unlike the old consumer's
    ~25 inbound/outbound types spread across one 1000+ line class, this hub
    only knows about presence/chat/observe/focus. Collaborative text editing
    and drawing are out of scope entirely (Collaboration Service / whiteboard
    service own those)."""
    msg_type = message.get("type")

    if msg_type == "ping":
        await presence.mark_online(
            r, classroom_id=classroom.id, user_id=user.user_id, connection_id=connection_id
        )
        return {"type": "pong"}

    # chat:send / observe:set / focus:set are added in app/ws/chat.py and
    # app/ws/focus.py and registered here - kept as a separate module per
    # concern rather than growing this function indefinitely.
    from app.ws import focus as focus_handlers
    from app.ws import chat as chat_handlers

    if msg_type == "chat:send":
        return await chat_handlers.handle_send(r=r, session_factory=session_factory, classroom=classroom, user=user, message=message)
    if msg_type == "observe:set":
        return await focus_handlers.handle_observe_set(r=r, classroom=classroom, user=user, message=message)
    if msg_type == "focus:set":
        return await focus_handlers.handle_focus_set(r=r, classroom=classroom, user=user, message=message)

    return {"type": "error", "code": "unknown_message_type"}
