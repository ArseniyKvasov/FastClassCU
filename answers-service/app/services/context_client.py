import uuid

import httpx

from app.config import settings
from app.models import ContextType
from fastclass_shared.http import propagate_headers


async def get_context_teacher_id(
    context_type: ContextType, context_id: uuid.UUID, bearer_token: str
) -> uuid.UUID | None:
    """Answers Service doesn't own classroom/assignment membership - it asks
    the owning service. The caller's own token is forwarded so the owning
    service's normal membership check applies (only a member/teacher gets a
    200 back at all); we then compare the returned teacher_id to the
    caller's own user_id locally rather than needing a second round-trip."""
    base_url = (
        settings.classroom_service_base_url
        if context_type == ContextType.classroom
        else settings.assignments_service_base_url
    )
    path = (
        f"/classrooms/{context_id}"
        if context_type == ContextType.classroom
        else f"/assignments/{context_id}"
    )
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=5) as client:
            response = await client.get(
                path, headers=propagate_headers({"Authorization": f"Bearer {bearer_token}"})
            )
            if response.status_code != 200:
                return None
            return uuid.UUID(response.json()["teacher_id"])
    except (httpx.HTTPError, KeyError, ValueError):
        return None
