import uuid

import jwt

from app.config import settings
from tests.conftest import make_token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_video_token_issued_to_member_with_correct_grants(api_client, monkeypatch):
    monkeypatch.setattr(settings, "livekit_api_secret", "test-livekit-secret")

    c = api_client
    teacher_token = make_token()
    r = c.post("/classrooms", json={"title": "Lesson"}, headers=_auth(teacher_token))
    classroom = r.json()

    r = c.get(f"/classrooms/{classroom['id']}/video-token", headers=_auth(teacher_token))
    assert r.status_code == 200, r.text
    token = r.json()["token"]

    claims = jwt.decode(token, "test-livekit-secret", algorithms=["HS256"])
    assert claims["video"]["room"] == f"classroom-{classroom['id']}"
    assert claims["video"]["roomAdmin"] is True  # teacher gets admin grant


def test_video_token_denied_when_communication_disabled(api_client):
    c = api_client
    teacher_token = make_token()
    r = c.post("/classrooms", json={"title": "Lesson"}, headers=_auth(teacher_token))
    classroom = r.json()

    c.patch(
        f"/classrooms/{classroom['id']}/settings",
        json={"communication_enabled": False},
        headers=_auth(teacher_token),
    )

    r = c.get(f"/classrooms/{classroom['id']}/video-token", headers=_auth(teacher_token))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "communication_disabled"


def test_video_token_denied_for_non_member(api_client):
    c = api_client
    teacher_token = make_token()
    r = c.post("/classrooms", json={"title": "Lesson"}, headers=_auth(teacher_token))
    classroom = r.json()

    outsider_token = make_token()
    r = c.get(f"/classrooms/{classroom['id']}/video-token", headers=_auth(outsider_token))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "not_a_member"


def test_whiteboard_token_role_reflects_teacher_vs_student(api_client):
    c = api_client
    teacher_token = make_token()
    r = c.post("/classrooms", json={"title": "Lesson"}, headers=_auth(teacher_token))
    classroom = r.json()

    student_id = uuid.uuid4()
    student_token = make_token(student_id)
    c.post(
        f"/classrooms/{classroom['id']}/join",
        json={"password": classroom["join_password"], "display_name": "Student"},
        headers=_auth(student_token),
    )

    r_teacher = c.get(f"/classrooms/{classroom['id']}/whiteboard-token", headers=_auth(teacher_token))
    r_student = c.get(f"/classrooms/{classroom['id']}/whiteboard-token", headers=_auth(student_token))

    teacher_claims = jwt.decode(r_teacher.json()["token"], settings.whiteboard_jwt_secret, algorithms=["HS256"])
    student_claims = jwt.decode(r_student.json()["token"], settings.whiteboard_jwt_secret, algorithms=["HS256"])

    assert teacher_claims["role"] == "moderator"
    assert student_claims["role"] == "editor"
