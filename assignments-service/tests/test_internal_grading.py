import uuid

from tests.conftest import make_token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_answer_scored_event_updates_grade_and_broadcasts(api_client):
    c = api_client
    teacher_token = make_token()
    task_a, task_b = str(uuid.uuid4()), str(uuid.uuid4())
    body = {
        "title": "HW",
        "lesson_id": str(uuid.uuid4()),
        "target_type": "link",
        "tasks": [
            {"task_id": task_a, "weight": 50},
            {"task_id": task_b, "weight": 50},
        ],
    }
    assignment = c.post("/assignments", json=body, headers=_auth(teacher_token)).json()

    student_token = make_token()
    session = c.post(
        f"/assignments/{assignment['id']}/sessions", headers=_auth(student_token)
    ).json()

    with c.websocket_connect(
        f"/ws/assignments/{assignment['id']}?token={teacher_token}"
    ) as teacher_ws:
        r = c.post(
            "/internal/events/answer-scored",
            json={"session_id": session["id"], "task_id": task_a, "correctness": 100.0},
        )
        assert r.status_code == 200
        assert r.json()["applied"] is True

        event = teacher_ws.receive_json()
        assert event["type"] == "session_grade_changed"
        assert event["grade"] == 100.0  # only one of two tasks scored so far

        c.post(
            "/internal/events/answer-scored",
            json={"session_id": session["id"], "task_id": task_b, "correctness": 0.0},
        )
        event2 = teacher_ws.receive_json()
        assert event2["grade"] == 50.0  # (100*50 + 0*50) / 100

    r = c.get(f"/sessions/{session['id']}", headers=_auth(teacher_token))
    assert float(r.json()["grade"]) == 50.0
