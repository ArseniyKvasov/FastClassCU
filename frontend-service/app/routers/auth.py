import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.config import settings
from app.cookies import clear_session_cookies, set_session_cookies
from app.deps import CurrentSession, get_optional_session

router = APIRouter(prefix="/auth", tags=["auth"])


async def _auth_request(method: str, path: str, **kwargs) -> httpx.Response:
    try:
        async with httpx.AsyncClient(base_url=settings.auth_service_base_url, timeout=5.0) as client:
            return await client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail={"code": "upstream_unavailable", "message": str(exc)}
        ) from exc


class SessionOut(BaseModel):
    authenticated: bool
    access_level: str | None = None
    user_id: str | None = None


class ProviderOut(BaseModel):
    key: str
    display_name: str


@router.get("/providers", response_model=list[ProviderOut])
async def list_providers() -> list[ProviderOut]:
    response = await _auth_request("GET", "/auth/providers")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail={"code": "upstream_error"})
    return response.json()


@router.get("/session", response_model=SessionOut)
async def get_session(session: CurrentSession | None = Depends(get_optional_session)) -> SessionOut:
    if session is None:
        return SessionOut(authenticated=False)
    return SessionOut(
        authenticated=True,
        access_level=session.access_level,
        user_id=str(session.user_id),
    )


@router.post("/guest", response_model=SessionOut)
async def create_guest_session(response: Response) -> SessionOut:
    upstream = await _auth_request("POST", "/auth/guest")
    if upstream.status_code >= 400:
        raise HTTPException(status_code=upstream.status_code, detail=upstream.json())

    body = upstream.json()
    set_session_cookies(
        response,
        access_token=body["access_token"],
        refresh_token=None,
        max_age=body["expires_in"],
    )
    return SessionOut(authenticated=True, access_level="guest", user_id=body["guest_session_id"])


@router.get("/{provider_key}/login")
async def oauth_login(
    provider_key: str, session: CurrentSession | None = Depends(get_optional_session)
) -> RedirectResponse:
    # Guest -> full upgrade: carry the guest session id through so auth-service
    # can link the new OAuth identity back to the guest's in-progress work.
    guest_session_id = str(session.user_id) if session and session.access_level == "guest" else None
    url = f"{settings.auth_service_base_url}/auth/{provider_key}/login"
    if guest_session_id:
        url += f"?guest_session_id={guest_session_id}"
    return RedirectResponse(url)


@router.get("/{provider_key}/callback")
async def oauth_callback(provider_key: str, code: str, state: str) -> RedirectResponse:
    """Bridge endpoint: browser lands here after the OAuth provider redirect.

    Requires auth-service's PUBLIC_BASE_URL to point at this BFF's public URL
    (not at auth-service itself) so its redirect_uri sends the browser here
    instead of to auth-service's own JSON-returning callback. That env change
    is part of Phase 1.2 (login modal) deployment config, not done yet.
    """
    upstream = await _auth_request(
        "GET", f"/auth/{provider_key}/callback", params={"code": code, "state": state}
    )
    if upstream.status_code >= 400:
        raise HTTPException(status_code=upstream.status_code, detail=upstream.json())

    body = upstream.json()
    redirect = RedirectResponse(url="/")
    set_session_cookies(
        redirect,
        access_token=body["access_token"],
        refresh_token=body["refresh_token"],
        max_age=body["expires_in"],
    )
    return redirect


@router.post("/logout")
async def logout(response: Response) -> dict:
    clear_session_cookies(response)
    return {"ok": True}
