import asyncio
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app import oauth
from app.config import settings
from app.models import GuestSession
from app.security import verify_token

FAKE_PROFILE = {"id": "ext-user-123", "email": "user@example.com", "name": "Test User"}


def _extract_state(location: str) -> str:
    return parse_qs(urlparse(location).query)["state"][0]


def test_unknown_provider_login_404s(client):
    r = client.get("/auth/does-not-exist/login")
    assert r.status_code == 404


def test_callback_rejects_bad_state(client):
    r = client.get("/auth/testprovider/callback", params={"code": "x", "state": "garbage"})
    assert r.status_code == 400


def test_full_oauth_flow_with_guest_upgrade(client, monkeypatch):
    async def fake_fetch_profile(provider, code):
        assert code == "fake-code"
        return FAKE_PROFILE

    monkeypatch.setattr(oauth, "fetch_profile", fake_fetch_profile)

    guest_resp = client.post("/auth/guest")
    guest_session_id = guest_resp.json()["guest_session_id"]

    login_resp = client.get(
        "/auth/testprovider/login", params={"guest_session_id": guest_session_id}
    )
    assert login_resp.status_code in (302, 307)
    assert login_resp.headers["location"].startswith("https://example.com/oauth/authorize")
    state = _extract_state(login_resp.headers["location"])

    callback_resp = client.get(
        "/auth/testprovider/callback", params={"code": "fake-code", "state": state}
    )
    assert callback_resp.status_code == 200
    tokens = callback_resp.json()

    claims = verify_token(tokens["access_token"])
    assert claims["access_level"] == "full"
    user_id = claims["sub"]

    async def _load_guest_session():
        # A dedicated engine/pool, disposed within the same asyncio.run() -
        # reusing app.db.engine here would hand us a connection checked out
        # on the TestClient's event loop, which asyncpg refuses to touch
        # from this separate loop.
        check_engine = create_async_engine(settings.database_url)
        try:
            async with check_engine.connect() as conn:
                result = await conn.execute(
                    select(GuestSession).where(GuestSession.id == guest_session_id)
                )
                return result.mappings().one()
        finally:
            await check_engine.dispose()

    session = asyncio.run(_load_guest_session())
    assert str(session["upgraded_to_user_id"]) == user_id

    async def _load_events():
        from app.models import AuthEvent

        check_engine = create_async_engine(settings.database_url)
        try:
            async with check_engine.connect() as conn:
                result = await conn.execute(
                    select(AuthEvent).where(AuthEvent.event_type == "user_upgraded")
                )
                return result.mappings().all()
        finally:
            await check_engine.dispose()

    events = asyncio.run(_load_events())
    matching = [e for e in events if e["payload"]["old_guest_session_id"] == guest_session_id]
    assert len(matching) == 1
    assert matching[0]["payload"]["new_user_id"] == user_id

    # Refresh rotates the token: old refresh token stops working, new one works.
    old_refresh = tokens["refresh_token"]
    refresh_resp = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert refresh_resp.status_code == 200
    new_tokens = refresh_resp.json()
    assert new_tokens["refresh_token"] != old_refresh

    reuse_resp = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse_resp.status_code == 401

    logout_resp = client.post("/auth/logout", json={"refresh_token": new_tokens["refresh_token"]})
    assert logout_resp.status_code == 200

    post_logout_refresh = client.post(
        "/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]}
    )
    assert post_logout_refresh.status_code == 401


def test_same_provider_identity_reuses_user(client, monkeypatch):
    async def fake_fetch_profile(provider, code):
        return FAKE_PROFILE

    monkeypatch.setattr(oauth, "fetch_profile", fake_fetch_profile)

    def login_once():
        state = oauth.encode_state("testprovider", None)
        resp = client.get(
            "/auth/testprovider/callback", params={"code": "any", "state": state}
        )
        assert resp.status_code == 200
        return verify_token(resp.json()["access_token"])["sub"]

    first_user_id = login_once()
    second_user_id = login_once()
    assert first_user_id == second_user_id
