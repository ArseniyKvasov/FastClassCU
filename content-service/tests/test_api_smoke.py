import uuid


def test_full_flow_through_http(api_client):
    c = api_client
    teacher = str(uuid.uuid4())
    student = str(uuid.uuid4())

    r = c.post("/lessons", json={"owner_id": teacher, "title": "Present Simple"})
    assert r.status_code == 200, r.text
    lesson = r.json()

    r = c.get(f"/lessons/{lesson['id']}/sections")
    assert r.status_code == 200
    section = r.json()[0]

    r = c.post(
        f"/sections/{section['id']}/tasks",
        json={"task_type": "text", "payload": {"content": "hello"}, "created_by": teacher},
    )
    assert r.status_code == 200, r.text
    task = r.json()
    assert task["payload"]["content"] == "hello"

    r = c.get(f"/tasks/{task['id']}")
    assert r.status_code == 200
    assert r.json()["payload"]["content"] == "hello"

    r = c.patch(
        f"/tasks/{task['id']}",
        json={"payload": {"content": "updated"}, "edited_by": teacher},
    )
    assert r.status_code == 200
    assert r.json()["payload"]["content"] == "updated"
    assert r.json()["current_content_id"] != task["current_content_id"]

    r = c.post(f"/lessons/{lesson['id']}/clone", json={"owner_id": teacher})
    assert r.status_code == 200
    clone = r.json()
    assert clone["derivation_type"] == "clone"

    r = c.post(f"/lessons/{clone['id']}/copy", json={"owner_id": student})
    assert r.status_code == 200
    copy = r.json()
    assert copy["derivation_type"] == "copy"

    # Duplicate copy request returns the same lesson, not a second one.
    r2 = c.post(f"/lessons/{clone['id']}/copy", json={"owner_id": student})
    assert r2.status_code == 200
    assert r2.json()["id"] == copy["id"]

    r = c.post(f"/lessons/{clone['id']}/sync")
    assert r.status_code == 200

    r = c.get(f"/quota/{teacher}")
    assert r.status_code == 200
    assert r.json()["storage_bytes"] > 0

    r = c.post("/admin/gc")
    assert r.status_code == 200

    r = c.post(
        "/collections", json={"owner_id": teacher, "title": "Grammar unit"}
    )
    assert r.status_code == 200
    collection = r.json()

    r = c.post(
        f"/collections/{collection['id']}/items", json={"lesson_id": lesson["id"]}
    )
    assert r.status_code == 204

    r = c.post(
        f"/lessons/{lesson['id']}/feedback",
        json={"user_id": student, "rating": 5, "comment": "great"},
    )
    assert r.status_code == 200

    r = c.get(f"/lessons/{lesson['id']}/feedback")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = c.delete(f"/tasks/{task['id']}")
    assert r.status_code == 204

    r = c.delete(f"/lessons/{lesson['id']}")
    assert r.status_code == 204

    r = c.get(f"/lessons/{lesson['id']}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "lesson_not_found"


def test_quota_exceeded_returns_409(api_client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "teacher_storage_limit_bytes", 5)

    c = api_client
    teacher = str(uuid.uuid4())
    r = c.post("/lessons", json={"owner_id": teacher, "title": "Lesson"})
    lesson = r.json()
    r = c.get(f"/lessons/{lesson['id']}/sections")
    section = r.json()[0]

    r = c.post(
        f"/sections/{section['id']}/tasks",
        json={
            "task_type": "text",
            "payload": {"content": "this content is definitely over five bytes"},
            "created_by": teacher,
        },
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "quota_exceeded"
