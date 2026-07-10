import json
import uuid

import httpx
import redis.asyncio as redis

from app.config import settings
from fastclass_shared import ServiceTokenProvider
from fastclass_shared.http import propagate_headers

_CACHE_TTL_SECONDS = 3600
_service_tokens = ServiceTokenProvider(
    auth_base_url=settings.auth_service_base_url,
    client_id=settings.service_client_id,
    client_secret=settings.service_client_secret,
    scopes=settings.content_service_scopes,
    enabled=bool(settings.service_client_secret),
)


class AnswerKeyNotFoundError(Exception):
    pass


def _cache_key(task_id: uuid.UUID) -> str:
    return f"answer_key:{task_id}"


async def get_answer_key(r: redis.Redis, *, task_id: uuid.UUID) -> dict:
    """Cached by task_id, content-addressed by content_id inside the cached
    value - content is immutable in Content Service, so a cache entry never
    goes stale on its own; it's only invalidated explicitly when Content
    Service tells us (via the 'task_updated' event) that this task now
    points at a different content_id - see services/cache_invalidation.py."""
    cached = await r.get(_cache_key(task_id))
    if cached is not None:
        return json.loads(cached)

    async with httpx.AsyncClient(base_url=settings.content_service_base_url, timeout=5) as client:
        headers = {"X-Service-Token": settings.content_service_token}
        headers.update(await _service_tokens.get_authorization_header())
        response = await client.get(
            f"/internal/tasks/{task_id}/answer-key",
            headers=propagate_headers(headers),
        )
        if response.status_code == 404:
            raise AnswerKeyNotFoundError(f"No such task: {task_id}")
        response.raise_for_status()
        data = response.json()

    await r.set(_cache_key(task_id), json.dumps(data), ex=_CACHE_TTL_SECONDS)
    return data


async def invalidate_answer_key(r: redis.Redis, *, task_id: uuid.UUID) -> None:
    await r.delete(_cache_key(task_id))
