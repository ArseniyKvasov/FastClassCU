import redis.asyncio as redis
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.deps import CurrentUser
from app.models import ChatMessage, Classroom
from app.ws.manager import publish


async def handle_send(
    *,
    r: redis.Redis,
    session_factory: async_sessionmaker[AsyncSession],
    classroom: Classroom,
    user: CurrentUser,
    message: dict,
) -> dict | None:
    body = (message.get("body") or "").strip()
    if not body:
        return {"type": "error", "code": "empty_message"}
    if len(body) > 4000:
        return {"type": "error", "code": "message_too_long"}

    async with session_factory() as db:
        chat_message = ChatMessage(classroom_id=classroom.id, sender_id=user.user_id, body=body)
        db.add(chat_message)
        await db.commit()
        await db.refresh(chat_message)

    await publish(
        r,
        classroom_id=classroom.id,
        message={
            "type": "chat:message",
            "id": str(chat_message.id),
            "sender_id": str(user.user_id),
            "body": body,
            "created_at": chat_message.created_at.isoformat(),
        },
    )
    return None
