import httpx

from app.config import settings
from fastclass_shared.http import propagate_headers


class WhiteboardServiceError(Exception):
    pass


def _admin_headers() -> dict:
    return propagate_headers(
        {"X-API-Key": settings.whiteboard_service_api_key, "Content-Type": "application/json"}
    )


async def update_board_drawing_access(board_id: str, allow_students_draw: bool) -> dict:
    url = f"{settings.whiteboard_base_url}/api/admin/board/{board_id}/drawing"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(
                url, headers=_admin_headers(), json={"allow_students_draw": allow_students_draw}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise WhiteboardServiceError(f"Failed to update board drawing access: {exc}") from exc


async def delete_board(board_id: str) -> dict:
    url = f"{settings.whiteboard_base_url}/api/admin/board/{board_id}"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.delete(url, headers=_admin_headers())
            if response.status_code == 404:
                return {"ok": True, "board_id": board_id, "not_found": True}
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise WhiteboardServiceError(f"Failed to delete board: {exc}") from exc
