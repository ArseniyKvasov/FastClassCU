import json
import uuid

import redis.asyncio as redis

from app.deps import CurrentUser
from app.models import Classroom
from app.ws.manager import publish


def _observed_key(classroom_id: uuid.UUID) -> str:
    return f"classroom:{classroom_id}:observed_student"


def _focus_key(classroom_id: uuid.UUID) -> str:
    return f"classroom:{classroom_id}:focus"


async def handle_observe_set(
    *, r: redis.Redis, classroom: Classroom, user: CurrentUser, message: dict
) -> dict | None:
    """UI-sync convenience only - which student the teacher is currently
    looking at, broadcast so all their own open tabs/panels agree. This is
    NEVER used to decide where an answer write lands (see Answers Service -
    every write carries an explicit student_id, precisely to avoid a race if
    the teacher switches students mid-request)."""
    if user.user_id != classroom.teacher_id:
        return {"type": "error", "code": "teacher_only"}

    student_id = message.get("student_id")
    key = _observed_key(classroom.id)
    if student_id is None:
        await r.delete(key)
    else:
        await r.set(key, str(student_id))

    await publish(
        r,
        classroom_id=classroom.id,
        message={"type": "observe:changed", "student_id": student_id},
    )
    return None


async def handle_focus_set(
    *, r: redis.Redis, classroom: Classroom, user: CurrentUser, message: dict
) -> dict | None:
    if user.user_id != classroom.teacher_id:
        return {"type": "error", "code": "teacher_only"}

    focus = {"section_id": message.get("section_id"), "task_id": message.get("task_id")}
    await r.set(_focus_key(classroom.id), json.dumps(focus))

    await publish(r, classroom_id=classroom.id, message={"type": "focus:changed", **focus})
    return None
