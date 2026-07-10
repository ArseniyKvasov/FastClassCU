import uuid

from tests.conftest import make_token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_join_with_correct_password_creates_membership(api_client):
    c = api_client
    teacher_token = make_token()
    r = c.post("/classrooms", json={"title": "Lesson"}, headers=_auth(teacher_token))
    assert r.status_code == 200, r.text
    classroom = r.json()
    password = classroom["join_password"]

    student_id = uuid.uuid4()
    student_token = make_token(student_id)
    r = c.post(
        f"/classrooms/{classroom['id']}/join",
        json={"password": password, "display_name": "Ivan Ivanov"},
        headers=_auth(student_token),
    )
    assert r.status_code == 200, r.text
    member = r.json()
    assert member["user_id"] == str(student_id)
    assert member["role"] == "student"


def test_join_with_wrong_password_is_rejected(api_client):
    c = api_client
    teacher_token = make_token()
    r = c.post("/classrooms", json={"title": "Lesson"}, headers=_auth(teacher_token))
    classroom = r.json()

    student_token = make_token()
    r = c.post(
        f"/classrooms/{classroom['id']}/join",
        json={"password": "WRONGPASS", "display_name": "X"},
        headers=_auth(student_token),
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "invalid_password"


def test_join_identity_comes_from_jwt_not_name_matching(api_client):
    """Closes the old system's account-takeover gap: two different users
    with the SAME display name must become two DIFFERENT memberships, keyed
    by their JWT user_id - never merged/confused by name."""
    c = api_client
    teacher_token = make_token()
    r = c.post("/classrooms", json={"title": "Lesson"}, headers=_auth(teacher_token))
    classroom = r.json()
    password = classroom["join_password"]

    alice_id = uuid.uuid4()
    mallory_id = uuid.uuid4()

    r1 = c.post(
        f"/classrooms/{classroom['id']}/join",
        json={"password": password, "display_name": "Ivan Ivanov"},
        headers=_auth(make_token(alice_id)),
    )
    r2 = c.post(
        f"/classrooms/{classroom['id']}/join",
        json={"password": password, "display_name": "Ivan Ivanov"},
        headers=_auth(make_token(mallory_id)),
    )
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["id"] != r2.json()["id"]
    assert r1.json()["user_id"] == str(alice_id)
    assert r2.json()["user_id"] == str(mallory_id)

    roster = c.get(
        f"/classrooms/{classroom['id']}/roster", headers=_auth(make_token(alice_id))
    ).json()
    assert len(roster["members"]) == 2


def test_per_ip_rate_limit_blocks_after_threshold(api_client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "join_attempts_per_ip_limit", 3)
    monkeypatch.setattr(settings, "join_attempts_per_ip_window_seconds", 3600)
    monkeypatch.setattr(settings, "join_attempts_global_per_classroom_limit", 1000)

    c = api_client
    r = c.post("/classrooms", json={"title": "Lesson"}, headers=_auth(make_token()))
    classroom_id = r.json()["id"]

    last = None
    for _ in range(3):
        last = c.post(
            f"/classrooms/{classroom_id}/join",
            json={"password": "WRONGPASS", "display_name": "X"},
            headers=_auth(make_token()),
        )
        assert last.status_code == 403

    blocked = c.post(
        f"/classrooms/{classroom_id}/join",
        json={"password": "WRONGPASS", "display_name": "X"},
        headers=_auth(make_token()),
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "too_many_attempts"
    assert "Retry-After" in blocked.headers


def test_global_lockout_blocks_even_new_ips(api_client, monkeypatch):
    """The distributed-attack defense: even if each individual (simulated)
    source stays under its own per-IP budget, once the classroom-wide
    aggregate is exceeded, ALL further attempts are locked out - including
    from an IP that hasn't made a single attempt yet."""
    from app.config import settings

    monkeypatch.setattr(settings, "join_attempts_per_ip_limit", 1000)
    monkeypatch.setattr(settings, "join_attempts_global_per_classroom_limit", 2)
    monkeypatch.setattr(settings, "join_attempts_global_per_classroom_window_seconds", 3600)
    monkeypatch.setattr(settings, "join_lockout_seconds", 900)

    c = api_client
    r = c.post("/classrooms", json={"title": "Lesson"}, headers=_auth(make_token()))
    classroom_id = r.json()["id"]
    correct_password = r.json()["join_password"]

    for _ in range(2):
        resp = c.post(
            f"/classrooms/{classroom_id}/join",
            json={"password": "WRONGPASS", "display_name": "X"},
            headers=_auth(make_token()),
        )
        assert resp.status_code == 403

    # A brand new "attacker" identity/IP - never made a request before -
    # still gets locked out because the classroom-wide budget is exhausted.
    fresh_attempt = c.post(
        f"/classrooms/{classroom_id}/join",
        json={"password": "WRONGPASS", "display_name": "X"},
        headers=_auth(make_token()),
    )
    assert fresh_attempt.status_code == 429

    # Even the CORRECT password is now blocked until the lockout expires -
    # otherwise the lockout would leak whether an attempt was about to
    # succeed, defeating its purpose.
    correct_but_locked = c.post(
        f"/classrooms/{classroom_id}/join",
        json={"password": correct_password, "display_name": "Legit Student"},
        headers=_auth(make_token()),
    )
    assert correct_but_locked.status_code == 429
