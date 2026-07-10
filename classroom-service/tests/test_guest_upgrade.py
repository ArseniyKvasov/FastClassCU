import uuid

from tests.conftest import make_token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_user_upgraded_event_repoints_membership(api_client):
    """Simulates the cross-service handoff: a guest joins a classroom, then
    Auth Service's 'user_upgraded' event (which a real deployment's relay
    would deliver here) arrives - membership must move to the new permanent
    user_id, not disappear."""
    c = api_client
    teacher_token = make_token()
    r = c.post("/classrooms", json={"title": "Lesson"}, headers=_auth(teacher_token))
    classroom = r.json()

    guest_session_id = uuid.uuid4()
    guest_token = make_token(guest_session_id, access_level="guest")
    r = c.post(
        f"/classrooms/{classroom['id']}/join",
        json={"password": classroom["join_password"], "display_name": "Guest Student"},
        headers=_auth(guest_token),
    )
    assert r.status_code == 200
    assert r.json()["user_id"] == str(guest_session_id)

    new_user_id = uuid.uuid4()
    r = c.post(
        "/internal/events/user-upgraded",
        json={"old_user_id": str(guest_session_id), "new_user_id": str(new_user_id)},
    )
    assert r.status_code == 200
    assert r.json()["memberships_updated"] == 1

    new_token = make_token(new_user_id)
    roster = c.get(
        f"/classrooms/{classroom['id']}/roster", headers=_auth(new_token)
    ).json()
    member_ids = {m["user_id"] for m in roster["members"]}
    assert str(new_user_id) in member_ids
    assert str(guest_session_id) not in member_ids


def test_user_upgraded_drops_guest_row_on_conflict(api_client):
    """If the upgraded account already has its own membership in the same
    classroom, the guest row is dropped rather than violating the unique
    constraint - the real membership wins, no duplicate/no crash."""
    c = api_client
    teacher_token = make_token()
    r = c.post("/classrooms", json={"title": "Lesson"}, headers=_auth(teacher_token))
    classroom = r.json()
    password = classroom["join_password"]

    guest_session_id = uuid.uuid4()
    new_user_id = uuid.uuid4()

    c.post(
        f"/classrooms/{classroom['id']}/join",
        json={"password": password, "display_name": "Guest Student"},
        headers=_auth(make_token(guest_session_id, access_level="guest")),
    )
    c.post(
        f"/classrooms/{classroom['id']}/join",
        json={"password": password, "display_name": "Real Account"},
        headers=_auth(make_token(new_user_id)),
    )

    r = c.post(
        "/internal/events/user-upgraded",
        json={"old_user_id": str(guest_session_id), "new_user_id": str(new_user_id)},
    )
    assert r.status_code == 200
    assert r.json()["memberships_updated"] == 0  # dropped, not updated

    roster = c.get(
        f"/classrooms/{classroom['id']}/roster", headers=_auth(make_token(new_user_id))
    ).json()
    assert len(roster["members"]) == 1
    assert roster["members"][0]["user_id"] == str(new_user_id)
