import base64
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings
from app.schemas import LessonBundle, LessonBundleOut, TaskRegistryOut
from fastclass_shared import ServiceTokenProvider
from fastclass_shared.http import propagate_headers


class ContentServiceError(Exception):
    pass


class LessonNotFoundError(ContentServiceError):
    pass


@dataclass
class GeneratedBinary:
    data: bytes
    mime_type: str
    filename: str


_service_tokens = ServiceTokenProvider(
    auth_base_url=settings.auth_service_base_url,
    client_id=settings.service_client_id,
    client_secret=settings.service_client_secret,
    scopes=settings.content_service_scopes,
    enabled=bool(settings.service_client_secret),
)


async def _request(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
) -> Any:
    request_headers = {"X-Service-Token": settings.content_service_token}
    request_headers.update(await _service_tokens.get_authorization_header())
    if headers:
        request_headers.update(headers)
    request_headers = propagate_headers(request_headers)

    async with httpx.AsyncClient(
        base_url=settings.content_service_base_url,
        timeout=settings.provider_timeout_seconds,
    ) as client:
        response = await client.request(
            method,
            path,
            headers=request_headers,
            json=json,
            files=files,
        )
    if response.status_code == 404:
        raise LessonNotFoundError(path)
    if response.status_code >= 400:
        raise ContentServiceError(response.text)
    return response.json() if response.content else None


async def get_task_registry() -> TaskRegistryOut:
    data = await _request("GET", "/internal/task-registry")
    return TaskRegistryOut.model_validate(data)


async def get_lesson_bundle(lesson_id: uuid.UUID) -> LessonBundleOut:
    data = await _request("GET", f"/internal/lessons/{lesson_id}/bundle")
    return LessonBundleOut.model_validate(data)


async def list_owner_lessons(owner_id: uuid.UUID, *, limit: int) -> list[LessonBundleOut]:
    data = await _request("GET", f"/internal/owners/{owner_id}/lessons?limit={limit}")
    return [LessonBundleOut.model_validate(item) for item in data]


async def create_lesson_draft(bundle: LessonBundle) -> LessonBundleOut:
    data = await _request("POST", "/internal/lessons/draft", json=bundle.model_dump(mode="json"))
    return LessonBundleOut.model_validate(data)


async def upload_generated_file(binary: GeneratedBinary) -> dict[str, Any]:
    files = {
        "file": (
            binary.filename,
            binary.data,
            binary.mime_type,
        )
    }
    return await _request("POST", "/files", files=files)


def decode_base64_payload(payload: str | None) -> bytes | None:
    if not payload:
        return None
    return base64.b64decode(payload)
