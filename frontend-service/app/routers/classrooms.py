from fastapi import APIRouter, Depends

from app.config import settings
from app.deps import CurrentSession, get_current_session
from app.upstream import raise_for_upstream_error, upstream_request

router = APIRouter(prefix="/classrooms", tags=["classrooms"])


@router.post("")
async def create_classroom(body: dict, session: CurrentSession = Depends(get_current_session)):
    response = await upstream_request(
        settings.classroom_service_base_url,
        "POST",
        "/classrooms",
        json=body,
        headers={"Authorization": f"Bearer {session.access_token}"},
    )
    raise_for_upstream_error(response)
    return response.json()
