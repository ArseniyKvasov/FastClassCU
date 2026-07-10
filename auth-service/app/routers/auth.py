import secrets

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, oauth
from app.config import settings
from app.db import get_db
from app.providers import PROVIDERS, get_field, get_provider
from app.service_clients import get_service_client
from app.schemas import (
    GuestTokenOut,
    LogoutRequest,
    ProviderOut,
    PublicKeyOut,
    RefreshRequest,
    ServiceTokenOut,
    TokenPair,
)
from app.security import mint_token, public_key_pem
from fastclass_shared import RateLimitExceeded, RateLimitRule, RedisRateLimiter, get_client_ip

router = APIRouter()
_oauth_callback_limiter = RedisRateLimiter(
    redis_url=settings.rate_limit_redis_url,
    service_name="auth-service",
)


@router.get("/public-key", response_model=PublicKeyOut)
def get_public_key() -> PublicKeyOut:
    return PublicKeyOut(public_key=public_key_pem())


@router.get("/providers", response_model=list[ProviderOut])
def list_providers() -> list[ProviderOut]:
    return [ProviderOut(key=p.key, display_name=p.display_name) for p in PROVIDERS.values()]


@router.post("/guest", response_model=GuestTokenOut)
async def create_guest_session(db: AsyncSession = Depends(get_db)) -> GuestTokenOut:
    session = await crud.create_guest_session(db, settings.guest_token_ttl_seconds)
    token = mint_token(
        subject=str(session.id),
        access_level="guest",
        ttl_seconds=settings.guest_token_ttl_seconds,
    )
    return GuestTokenOut(
        access_token=token,
        expires_in=settings.guest_token_ttl_seconds,
        guest_session_id=str(session.id),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    token = await crud.consume_refresh_token(db, body.refresh_token)
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Rotate: revoke the used refresh token, issue a fresh pair.
    await crud.revoke_refresh_token(db, body.refresh_token)
    new_refresh = await crud.issue_refresh_token(
        db, token.user_id, settings.refresh_token_ttl_seconds
    )
    access = mint_token(
        subject=str(token.user_id),
        access_level="full",
        ttl_seconds=settings.access_token_ttl_seconds,
    )
    return TokenPair(
        access_token=access,
        refresh_token=new_refresh,
        expires_in=settings.access_token_ttl_seconds,
    )


@router.post("/logout")
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)) -> dict:
    await crud.revoke_refresh_token(db, body.refresh_token)
    return {"ok": True}


@router.post("/service-token", response_model=ServiceTokenOut)
async def issue_service_token(
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    scope: str = Form(default=""),
) -> ServiceTokenOut:
    if grant_type != "client_credentials":
        raise HTTPException(status_code=400, detail={"code": "unsupported_grant_type"})

    client = get_service_client(client_id)
    if client is None or not secrets.compare_digest(client.client_secret, client_secret):
        raise HTTPException(status_code=401, detail={"code": "invalid_client"})

    requested_scopes = {item for item in scope.split() if item}
    allowed_scopes = set(client.scopes)
    if requested_scopes and not requested_scopes.issubset(allowed_scopes):
        raise HTTPException(status_code=403, detail={"code": "invalid_scope"})

    final_scopes = sorted(requested_scopes or allowed_scopes)
    access = mint_token(
        subject=client.client_id,
        access_level="service",
        ttl_seconds=settings.service_access_token_ttl_seconds,
        extra_claims={
            "token_use": "service",
            "scope": " ".join(final_scopes),
            "client_id": client.client_id,
        },
    )
    return ServiceTokenOut(
        access_token=access,
        expires_in=settings.service_access_token_ttl_seconds,
    )


@router.get("/{provider_key}/login")
async def oauth_login(provider_key: str, guest_session_id: str | None = Query(default=None)):
    provider = get_provider(provider_key)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider_key}'")

    state = oauth.encode_state(provider_key, guest_session_id)
    url = await oauth.build_authorization_url(provider, state)
    return RedirectResponse(url)


@router.get("/{provider_key}/callback", response_model=TokenPair)
async def oauth_callback(
    provider_key: str,
    code: str,
    state: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    try:
        await _oauth_callback_limiter.hit(
            RateLimitRule(
                name="oauth-callback",
                limit=settings.oauth_callback_rate_limit,
                window_seconds=settings.oauth_callback_window_seconds,
            ),
            get_client_ip(request),
            provider_key,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={"code": "too_many_requests", "retry_after_seconds": exc.retry_after_seconds},
        )

    provider = get_provider(provider_key)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider_key}'")

    try:
        state_claims = oauth.decode_state(state)
    except (ExpiredSignatureError, InvalidTokenError):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    if state_claims.get("provider_key") != provider_key:
        raise HTTPException(status_code=400, detail="State does not match provider")

    profile = await oauth.fetch_profile(provider, code)

    provider_user_id = get_field(profile, provider.user_id_field)
    if provider_user_id is None:
        raise HTTPException(status_code=502, detail="Provider response missing user id")

    email = get_field(profile, provider.email_field)
    display_name = get_field(profile, provider.name_field)

    user = await crud.get_or_create_user(
        db,
        provider=provider_key,
        provider_user_id=str(provider_user_id),
        email=email,
        display_name=display_name,
    )

    guest_session_id = state_claims.get("guest_session_id")
    if guest_session_id:
        await crud.upgrade_guest_to_full(db, guest_session_id, user.id)

    refresh = await crud.issue_refresh_token(db, user.id, settings.refresh_token_ttl_seconds)
    access = mint_token(
        subject=str(user.id),
        access_level="full",
        role=user.role,
        ttl_seconds=settings.access_token_ttl_seconds,
    )
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_ttl_seconds,
    )
