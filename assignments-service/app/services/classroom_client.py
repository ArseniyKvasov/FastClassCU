import uuid

import httpx

from app.config import settings
from fastclass_shared.http import propagate_headers


async def is_classroom_member(classroom_id: uuid.UUID, bearer_token: str) -> bool:
    """Forwards the student's own token to Classroom Service - if they're
    genuinely a member (or the teacher), GET /classrooms/{id} succeeds.
    Synchronous by necessity: whether someone can start a session right now
    can't be answered from an eventually-consistent local projection."""
    try:
        async with httpx.AsyncClient(
            base_url=settings.classroom_service_base_url, timeout=5
        ) as client:
            response = await client.get(
                f"/classrooms/{classroom_id}",
                headers=propagate_headers({"Authorization": f"Bearer {bearer_token}"}),
            )
            return response.status_code == 200
    except httpx.HTTPError:
        return False
