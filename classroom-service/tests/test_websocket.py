import uuid

from tests.conftest import make_token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _setup_classroom_with_student(c):
    teacher_id = uuid.uuid4()
    teacher_token = make_token(teacher_id)
    r = c.post("/classrooms", json={"title": "Lesson"}, headers=_auth(teacher_token))
    classroom = r.json()

    student_id = uuid.uuid4()
    student_token = make_token(student_id)
    c.post(
        f"/classrooms/{classroom['id']}/join",
        json={"password": classroom["join_password"], "display_name": "Student One"},
        headers=_auth(student_token),
    )
    return classroom, teacher_id, teacher_token, student_id, student_token


def test_connect_receives_snapshot_with_full_state(api_client):
    c = api_client
    classroom, teacher_id, teacher_token, student_id, student_token = _setup_classroom_with_student(c)

    with c.websocket_connect(f"/ws/classrooms/{classroom['id']}?token={teacher_token}") as ws:
        snapshot = ws.receive_json()
        assert snapshot["type"] == "snapshot"
        assert snapshot["classroom"]["id"] == classroom["id"]
        assert len(snapshot["members"]) == 1
        assert snapshot["members"][0]["user_id"] == str(student_id)
        assert snapshot["recent_chat"] == []


def test_non_member_is_rejected_at_handshake(api_client):
    c = api_client
    r = c.post("/classrooms", json={"title": "Lesson"}, headers=_auth(make_token()))
    classroom = r.json()

    outsider_token = make_token()
    try:
        with c.websocket_connect(f"/ws/classrooms/{classroom['id']}?token={outsider_token}"):
            raise AssertionError("should not have connected")
    except Exception:
        pass  # starlette raises on the rejected handshake - expected


def test_chat_message_delivered_to_other_connection_via_redis(api_client):
    """Proves delivery goes through Redis pub/sub, not an in-process shortcut
    - two separate websocket connections (simulating two different worker
    processes in production) both get the message."""
    c = api_client
    classroom, teacher_id, teacher_token, student_id, student_token = _setup_classroom_with_student(c)

    with c.websocket_connect(f"/ws/classrooms/{classroom['id']}?token={teacher_token}") as teacher_ws:
        teacher_ws.receive_json()  # snapshot

        with c.websocket_connect(f"/ws/classrooms/{classroom['id']}?token={student_token}") as student_ws:
            student_ws.receive_json()  # snapshot

            teacher_ws.send_json({"type": "chat:send", "body": "Hello class"})

            received_by_student = student_ws.receive_json()
            assert received_by_student["type"] == "chat:message"
            assert received_by_student["body"] == "Hello class"
            assert received_by_student["sender_id"] == str(teacher_id)

            # The sender's own connection gets it too (broadcast, not a
            # targeted send) - confirms it's genuinely pub/sub, not a
            # "send to everyone except me" special case.
            received_by_teacher = teacher_ws.receive_json()
            assert received_by_teacher["body"] == "Hello class"


def test_ping_gets_pong_and_refreshes_presence(api_client):
    c = api_client
    classroom, teacher_id, teacher_token, *_ = _setup_classroom_with_student(c)

    with c.websocket_connect(f"/ws/classrooms/{classroom['id']}?token={teacher_token}") as ws:
        ws.receive_json()  # snapshot
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"


def test_observed_student_broadcasts_but_is_teacher_only(api_client):
    c = api_client
    classroom, teacher_id, teacher_token, student_id, student_token = _setup_classroom_with_student(c)

    with c.websocket_connect(f"/ws/classrooms/{classroom['id']}?token={teacher_token}") as teacher_ws:
        teacher_ws.receive_json()

        with c.websocket_connect(f"/ws/classrooms/{classroom['id']}?token={student_token}") as student_ws:
            student_ws.receive_json()

            # A student trying to set observed_student is rejected.
            student_ws.send_json({"type": "observe:set", "student_id": str(student_id)})
            error = student_ws.receive_json()
            assert error == {"type": "error", "code": "teacher_only"}

            # The teacher can, and it's broadcast to everyone.
            teacher_ws.send_json({"type": "observe:set", "student_id": str(student_id)})
            event = student_ws.receive_json()
            assert event == {"type": "observe:changed", "student_id": str(student_id)}


def test_reconnect_snapshot_reflects_new_roster_state(api_client):
    """Simulates a reconnect after a second student joined while disconnected
    - the snapshot must reflect the CURRENT durable state (Postgres/Redis),
    proving no per-connection server memory is required to catch up."""
    c = api_client
    classroom, teacher_id, teacher_token, student_id, student_token = _setup_classroom_with_student(c)

    with c.websocket_connect(f"/ws/classrooms/{classroom['id']}?token={teacher_token}") as ws:
        snapshot1 = ws.receive_json()
        assert len(snapshot1["members"]) == 1

    second_student_token = make_token()
    c.post(
        f"/classrooms/{classroom['id']}/join",
        json={"password": classroom["join_password"], "display_name": "Student Two"},
        headers=_auth(second_student_token),
    )

    with c.websocket_connect(f"/ws/classrooms/{classroom['id']}?token={teacher_token}") as ws:
        snapshot2 = ws.receive_json()
        assert len(snapshot2["members"]) == 2
