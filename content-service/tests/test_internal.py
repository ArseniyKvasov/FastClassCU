import uuid
from pathlib import Path

import jwt

from app.config import settings


def test_answer_key_requires_service_token(api_client):
    c = api_client
    r = c.post("/lessons", json={"owner_id": str(uuid.uuid4()), "title": "Lesson"})
    lesson = r.json()
    section = c.get(f"/lessons/{lesson['id']}/sections").json()[0]
    task = c.post(
        f"/sections/{section['id']}/tasks",
        json={
            "task_type": "test",
            "payload": {
                "questions": [
                    {"question": "2+2?", "options": ["3", "4"], "correct_index": 1}
                ]
            },
            "created_by": lesson["owner_id"],
        },
    ).json()

    r = c.get(f"/internal/tasks/{task['id']}/answer-key")
    assert r.status_code == 401

    r = c.get(
        f"/internal/tasks/{task['id']}/answer-key",
        headers={"X-Service-Token": "dev-insecure-service-token"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["task_type"] == "test"
    assert body["answer_key"]["questions"][0]["correct_index"] == 1


def test_answer_key_accepts_service_jwt(api_client, monkeypatch):
    monkeypatch.setattr(
        settings,
        "jwt_public_key_path",
        str(Path("/Users/arseniy/PycharmProjects/FastClass/auth-service/keys/public.pem")),
    )
    monkeypatch.setattr(settings, "allow_legacy_internal_service_token", False)

    c = api_client
    r = c.post("/lessons", json={"owner_id": str(uuid.uuid4()), "title": "Lesson"})
    lesson = r.json()
    section = c.get(f"/lessons/{lesson['id']}/sections").json()[0]
    task = c.post(
        f"/sections/{section['id']}/tasks",
        json={
            "task_type": "test",
            "payload": {
                "questions": [
                    {"question": "2+2?", "options": ["3", "4"], "correct_index": 1}
                ]
            },
            "created_by": lesson["owner_id"],
        },
    ).json()

    private_key = Path(
        "/Users/arseniy/PycharmProjects/FastClass/auth-service/keys/private.pem"
    ).read_text()
    token = jwt.encode(
        {
            "sub": "answers-service",
            "iss": settings.jwt_issuer,
            "access_level": "service",
            "token_use": "service",
            "scope": "content:answer-key:read",
        },
        private_key,
        algorithm="RS256",
    )

    r = c.get(
        f"/internal/tasks/{task['id']}/answer-key",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
