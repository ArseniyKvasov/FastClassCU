import uuid

from fastapi import APIRouter, Depends

from app.config import settings
from app.deps import CurrentSession, get_current_session
from app.upstream import raise_for_upstream_error, upstream_request

router = APIRouter(tags=["lessons"])


async def _content_request(method: str, path: str, **kwargs):
    response = await upstream_request(settings.content_service_base_url, method, path, **kwargs)
    raise_for_upstream_error(response)
    return response.json()


@router.get("/lessons")
async def list_my_lessons(session: CurrentSession = Depends(get_current_session)):
    """Every lesson the current user owns - originals, clones they've added,
    and copies they've made. Used to populate step 1 of the homework
    wizard's lesson picker."""
    return await _content_request("GET", "/lessons", params={"owner_id": str(session.user_id)})


@router.get("/lessons/{lesson_id}/sections")
async def list_lesson_sections(lesson_id: uuid.UUID, _session: CurrentSession = Depends(get_current_session)):
    return await _content_request("GET", f"/lessons/{lesson_id}/sections")


@router.get("/sections/{section_id}/tasks")
async def list_section_tasks(section_id: uuid.UUID, _session: CurrentSession = Depends(get_current_session)):
    return await _content_request("GET", f"/sections/{section_id}/tasks")


@router.post("/lessons/{lesson_id}/copy")
async def copy_lesson(lesson_id: uuid.UUID, session: CurrentSession = Depends(get_current_session)):
    """Idempotent: content-service returns the caller's existing copy of
    this lesson if one already exists instead of erroring, so it's safe to
    call every time the homework wizard commits to issuing an assignment
    off a clone - no separate "does a copy already exist" check needed."""
    return await _content_request(
        "POST", f"/lessons/{lesson_id}/copy", json={"owner_id": str(session.user_id)}
    )


@router.get("/quota")
async def get_my_quota(session: CurrentSession = Depends(get_current_session)):
    return await _content_request("GET", f"/quota/{session.user_id}")
