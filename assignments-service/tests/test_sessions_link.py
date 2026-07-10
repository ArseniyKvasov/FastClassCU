import uuid

from tests.conftest import make_token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_link_assignment(c, teacher_token, **overrides):
    task_id = str(uuid.uuid4())
    body = {
        "title": "Homework 1",
        "lesson_id": str(uuid.uuid4()),
        "attempts_limit": 1,
        "target_type": "link",
        "tasks": [{"task_id": task_id, "weight": 100}],
        **overrides,
    }
    r = c.post("/assignments", json=body, headers=_auth(teacher_token))
    assert r.status_code == 200, r.text
    return r.json()


def test_student_can_start_and_submit_session_via_link(api_client):
    c = api_client
    teacher_token = make_token()
    assignment = _create_link_assignment(c, teacher_token)

    student_token = make_token()
    r = c.post(f"/assignments/{assignment['id']}/sessions", headers=_auth(student_token))
    assert r.status_code == 200, r.text
    session = r.json()
    assert session["status"] == "active"
    assert session["attempt_number"] == 1

    r = c.post(f"/sessions/{session['id']}/submit", headers=_auth(student_token))
    assert r.status_code == 200
    assert r.json()["status"] == "submitted"


def test_attempts_limit_enforced(api_client):
    c = api_client
    teacher_token = make_token()
    assignment = _create_link_assignment(c, teacher_token, attempts_limit=1)

    student_token = make_token()
    r1 = c.post(f"/assignments/{assignment['id']}/sessions", headers=_auth(student_token))
    assert r1.status_code == 200

    r2 = c.post(f"/assignments/{assignment['id']}/sessions", headers=_auth(student_token))
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "attempts_exceeded"


def test_multiple_attempts_allowed_when_limit_raised(api_client):
    c = api_client
    teacher_token = make_token()
    assignment = _create_link_assignment(c, teacher_token, attempts_limit=2)

    student_token = make_token()
    r1 = c.post(f"/assignments/{assignment['id']}/sessions", headers=_auth(student_token))
    c.post(f"/sessions/{r1.json()['id']}/submit", headers=_auth(student_token))

    r2 = c.post(f"/assignments/{assignment['id']}/sessions", headers=_auth(student_token))
    assert r2.status_code == 200
    assert r2.json()["attempt_number"] == 2

    r3 = c.post(f"/assignments/{assignment['id']}/sessions", headers=_auth(student_token))
    assert r3.status_code == 409


def test_only_owner_or_teacher_can_view_session(api_client):
    c = api_client
    teacher_token = make_token()
    assignment = _create_link_assignment(c, teacher_token)

    student_token = make_token()
    session = c.post(
        f"/assignments/{assignment['id']}/sessions", headers=_auth(student_token)
    ).json()

    outsider_token = make_token()
    r = c.get(f"/sessions/{session['id']}", headers=_auth(outsider_token))
    assert r.status_code == 403

    r_owner = c.get(f"/sessions/{session['id']}", headers=_auth(student_token))
    assert r_owner.status_code == 200

    r_teacher = c.get(f"/sessions/{session['id']}", headers=_auth(teacher_token))
    assert r_teacher.status_code == 200


def test_time_left_reflects_time_limit(api_client):
    c = api_client
    teacher_token = make_token()
    assignment = _create_link_assignment(c, teacher_token, time_limit_minutes=10)

    student_token = make_token()
    r = c.post(f"/assignments/{assignment['id']}/sessions", headers=_auth(student_token))
    session = r.json()
    assert session["time_left_seconds"] is not None
    assert 0 < session["time_left_seconds"] <= 600
