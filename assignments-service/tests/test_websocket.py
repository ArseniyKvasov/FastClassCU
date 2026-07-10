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


def test_teacher_receives_submission_notification(api_client):
    c = api_client
    teacher_token = make_token()
    assignment, session, student_token = _create_and_start(c, teacher_token)

    with c.websocket_connect(
        f"/ws/assignments/{assignment['id']}?token={teacher_token}"
    ) as teacher_ws:
        c.post(f"/sessions/{session['id']}/submit", headers=_auth(student_token))

        event = teacher_ws.receive_json()
        assert event["type"] == "session_submitted"
        assert event["session_id"] == session["id"]


def test_student_receives_grade_notification(api_client):
    c = api_client
    teacher_token = make_token()
    assignment, session, student_token = _create_and_start(c, teacher_token)

    with c.websocket_connect(
        f"/ws/assignments/{assignment['id']}?token={student_token}"
    ) as student_ws:
        c.patch(
            f"/sessions/{session['id']}/grade",
            json={"grade": 95},
            headers=_auth(teacher_token),
        )
        event = student_ws.receive_json()
        assert event["type"] == "session_grade_changed"
        assert event["grade"] == 95.0


def test_outsider_cannot_connect(api_client):
    c = api_client
    teacher_token = make_token()
    assignment, session, student_token = _create_and_start(c, teacher_token)

    outsider_token = make_token()
    try:
        with c.websocket_connect(f"/ws/assignments/{assignment['id']}?token={outsider_token}"):
            raise AssertionError("should not have connected")
    except Exception:
        pass


def test_ping_pong(api_client):
    c = api_client
    teacher_token = make_token()
    assignment, session, student_token = _create_and_start(c, teacher_token)

    with c.websocket_connect(f"/ws/assignments/{assignment['id']}?token={teacher_token}") as ws:
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong == {"type": "pong"}
