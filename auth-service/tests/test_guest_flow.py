from app.security import verify_token


def test_create_guest_session_issues_guest_token(client):
    r = client.post("/auth/guest")
    assert r.status_code == 200
    body = r.json()
    assert body["guest_session_id"]

    claims = verify_token(body["access_token"])
    assert claims["access_level"] == "guest"
    assert claims["sub"] == body["guest_session_id"]
