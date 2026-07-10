import asyncio
import json
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.models import Assignment, AssignmentSession
from app.redis_client import get_redis_client
from app.security import InvalidTokenError, verify_token
from app.ws.manager import channel_name

router = APIRouter()


async def _authenticate(token: str) -> uuid.UUID | None:
    try:
        claims = verify_token(token)
    except InvalidTokenError:
        return None
    return uuid.UUID(claims["sub"])


async def _has_access(assignment: Assignment, user_id: uuid.UUID) -> bool:
    if assignment.teacher_id == user_id:
        return True
    async with SessionLocal() as db:
        count = await db.scalar(
            select(func.count()).select_from(AssignmentSession).where(
                AssignmentSession.assignment_id == assignment.id,
                AssignmentSession.student_id == user_id,
            )
        )
    return count > 0


@router.websocket("/ws/assignments/{assignment_id}")
async def assignment_socket(
    websocket: WebSocket, assignment_id: uuid.UUID, token: str = Query(...)
):
    """Deliberately minimal - notifications only (new submission, grade
    posted), no chat/presence/collaborative state. Same single-delivery-path
    rule as Classroom Service's hub (Redis pub/sub, nothing in process
    memory), just with far less surface area since this service doesn't need
    more than that."""
    user_id = await _authenticate(token)
    if user_id is None:
        await websocket.close(code=4401)
        return

    async with SessionLocal() as db:
        assignment = await db.get(Assignment, assignment_id)
    if assignment is None:
        await websocket.close(code=4404)
        return

    if not await _has_access(assignment, user_id):
        await websocket.close(code=4403)
        return

    await websocket.accept()

    r = get_redis_client()
    pubsub = r.pubsub()
    await pubsub.subscribe(channel_name(assignment_id))

    async def forward_pubsub_to_client() -> None:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            await websocket.send_text(message["data"])

    forward_task = asyncio.create_task(forward_pubsub_to_client())

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
                continue

            if incoming.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        forward_task.cancel()
        await pubsub.unsubscribe(channel_name(assignment_id))
        await pubsub.aclose()
        await r.aclose()
