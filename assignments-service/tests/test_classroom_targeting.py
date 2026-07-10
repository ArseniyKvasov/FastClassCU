import uuid

from tests.conftest import make_token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_classroom_targeted_assignment_requires_membership(api_client, monkeypatch):
    import app.routers.sessions as sessions_router

    async def fake_is_member(classroom_id, token):
        return False

    monkeypatch.setattr(sessions_router, "is_classroom_member", fake_is_member)

    c = api_client
    teacher_token = make_token()
    classroom_id = uuid.uuid4()
    body = {
        "title": "HW",
        "lesson_id": str(uuid.uuid4()),
        "target_type": "classroom",
        "target_classroom_id": str(classroom_id),
        "tasks": [{"task_id": str(uuid.uuid4()), "weight": 100}],
    }
    assignment = c.post("/assignments", json=body, headers=_auth(teacher_token)).json()

    student_token = make_token()
    r = c.post(f"/assignments/{assignment['id']}/sessions", headers=_auth(student_token))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "not_a_classroom_member"


def test_classroom_targeted_assignment_allows_verified_member(api_client, monkeypatch):
    import app.routers.sessions as sessions_router

    async def fake_is_member(classroom_id, token):
        return True

    monkeypatch.setattr(sessions_router, "is_classroom_member", fake_is_member)

    c = api_client
    teacher_token = make_token()
    classroom_id = uuid.uuid4()
    body = {
        "title": "HW",
        "lesson_id": str(uuid.uuid4()),
        "target_type": "classroom",
        "target_classroom_id": str(classroom_id),
        "tasks": [{"task_id": str(uuid.uuid4()), "weight": 100}],
    }
    assignment = c.post("/assignments", json=body, headers=_auth(teacher_token)).json()

    student_token = make_token()
    r = c.post(f"/assignments/{assignment['id']}/sessions", headers=_auth(student_token))
    assert r.status_code == 200


def test_classroom_target_requires_classroom_id(api_client):
    c = api_client
    teacher_token = make_token()
    body = {
        "title": "HW",
        "lesson_id": str(uuid.uuid4()),
        "target_type": "classroom",
        "tasks": [],
    }
    r = c.post("/assignments", json=body, headers=_auth(teacher_token))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_request"
