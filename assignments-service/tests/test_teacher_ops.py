import uuid

from tests.conftest import make_token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_and_start(c, teacher_token):
    body = {
        "title": "HW",
        "lesson_id": str(uuid.uuid4()),
        "target_type": "link",
        "tasks": [{"task_id": str(uuid.uuid4()), "weight": 100}],
    }
    assignment = c.post("/assignments", json=body, headers=_auth(teacher_token)).json()
    student_token = make_token()
    session = c.post(
        f"/assignments/{assignment['id']}/sessions", headers=_auth(student_token)
    ).json()
    return assignment, session, student_token


def test_teacher_can_set_status_comment_and_grade(api_client):
    c = api_client
    teacher_token = make_token()
    assignment, session, student_token = _create_and_start(c, teacher_token)

    r = c.patch(
        f"/sessions/{session['id']}/status", json={"status": "checked"}, headers=_auth(teacher_token)
    )
    assert r.status_code == 200
    assert r.json()["status"] == "checked"

    r = c.patch(
        f"/sessions/{session['id']}/comment",
        json={"comment": "Good work"},
        headers=_auth(teacher_token),
    )
    assert r.status_code == 200
    assert r.json()["teacher_comment"] == "Good work"

    r = c.patch(
        f"/sessions/{session['id']}/grade", json={"grade": 87.5}, headers=_auth(teacher_token)
    )
    assert r.status_code == 200
    assert float(r.json()["grade"]) == 87.5


def test_student_cannot_perform_teacher_operations(api_client):
    c = api_client
    teacher_token = make_token()
    assignment, session, student_token = _create_and_start(c, teacher_token)

    r = c.patch(
        f"/sessions/{session['id']}/status", json={"status": "checked"}, headers=_auth(student_token)
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "teacher_only"


def test_teacher_can_list_all_sessions_but_student_cannot(api_client):
    c = api_client
    teacher_token = make_token()
    assignment, session, student_token = _create_and_start(c, teacher_token)

    r = c.get(f"/assignments/{assignment['id']}/sessions", headers=_auth(teacher_token))
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = c.get(f"/assignments/{assignment['id']}/sessions", headers=_auth(student_token))
    assert r.status_code == 403
