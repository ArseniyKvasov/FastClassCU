import json
import uuid

from tests.conftest import make_token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_collab_snapshot_requires_service_token(api_client):
    r = api_client.post(
        "/internal/collab-snapshot",
        json={
            "task_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "context_type": "classroom",
            "context_id": str(uuid.uuid4()),
            "plain_text": "hello",
            "document_json": {"type": "doc", "content": []},
            "revision": 1,
        },
    )
    assert r.status_code == 401


def test_collab_snapshot_persists_writing_task_text(api_client, monkeypatch):
    import app.services.content_client as content_client

    task_id = uuid.uuid4()
    key = {
        "task_id": str(task_id),
        "content_id": str(uuid.uuid4()),
        "task_type": "writing_task",
        "answer_key": {},
    }

    async def fake_get_answer_key(r, *, task_id):
        return key

    monkeypatch.setattr(content_client, "get_answer_key", fake_get_answer_key)

    c = api_client
    user_id = uuid.uuid4()
    r = c.post(
        "/internal/collab-snapshot",
        json={
            "task_id": str(task_id),
            "user_id": str(user_id),
            "context_type": "classroom",
            "context_id": str(uuid.uuid4()),
            "plain_text": "Once upon a time...",
            "document_json": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Once upon a time..."}],
                    }
                ],
            },
            "revision": 3,
        },
        headers={"X-Service-Token": "dev-insecure-service-token"},
    )
    assert r.status_code == 200, r.text
    answer = r.json()
    assert answer["task_type"] == "writing_task"
    assert answer["payload"]["plain_text"] == "Once upon a time..."
    assert answer["payload"]["document_json"]["type"] == "doc"
    assert answer["payload"]["revision"] == 3
    assert answer["is_checked"] is False  # subjective, never auto-checked

    fetch = c.get(
        "/internal/collab-snapshot",
        params={
            "task_id": str(task_id),
            "user_id": str(user_id),
            "context_type": "classroom",
            "context_id": answer["context_id"],
        },
        headers={"X-Service-Token": "dev-insecure-service-token"},
    )
    assert fetch.status_code == 200, fetch.text
    assert fetch.json()["payload"]["plain_text"] == "Once upon a time..."


async def test_task_updated_event_invalidates_cache(redis_client, monkeypatch):
    import httpx

    from app.services import content_client

    task_id = uuid.uuid4()
    call_count = {"n": 0}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            call_count["n"] += 1
            return {
                "task_id": str(task_id),
                "content_id": str(uuid.uuid4()),
                "task_type": "test",
                "answer_key": {"questions": []},
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, path, headers=None):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: FakeClient())

    first = await content_client.get_answer_key(redis_client, task_id=task_id)
    second = await content_client.get_answer_key(redis_client, task_id=task_id)
    assert call_count["n"] == 1  # second call served from cache

    await content_client.invalidate_answer_key(redis_client, task_id=task_id)

    await content_client.get_answer_key(redis_client, task_id=task_id)
    assert call_count["n"] == 2  # cache miss after invalidation, re-fetched
