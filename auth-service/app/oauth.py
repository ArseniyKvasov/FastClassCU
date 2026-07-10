import time
from typing import Any

import jwt
from authlib.integrations.httpx_client import AsyncOAuth2Client

from app.config import settings
from app.providers import ProviderConfig


def encode_state(provider_key: str, guest_session_id: str | None) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "provider_key": provider_key,
        "iat": now,
        "exp": now + settings.oauth_state_ttl_seconds,
    }
    if guest_session_id:
        payload["guest_session_id"] = guest_session_id
    return jwt.encode(payload, settings.oauth_state_secret, algorithm="HS256")


def decode_state(state: str) -> dict:
    return jwt.decode(state, settings.oauth_state_secret, algorithms=["HS256"])


def redirect_uri_for(provider_key: str) -> str:
    return f"{settings.public_base_url}/auth/{provider_key}/callback"


async def build_authorization_url(provider: ProviderConfig, state: str) -> str:
    client = AsyncOAuth2Client(
        client_id=provider.client_id,
        scope=provider.scope or None,
        redirect_uri=redirect_uri_for(provider.key),
    )
    uri, _ = client.create_authorization_url(provider.authorize_url, state=state)
    return uri


async def fetch_profile(provider: ProviderConfig, code: str) -> dict:
    """Exchanges the auth code for a provider access token, then calls the
    provider's userinfo endpoint. Generic across providers by design - any
    provider-specific quirk (VK wanting access_token as a query param rather
    than an Authorization header, say) belongs in providers.yaml as an extra
    param, not as a new code path here."""
    async with AsyncOAuth2Client(
        client_id=provider.client_id,
        client_secret=provider.client_secret,
        redirect_uri=redirect_uri_for(provider.key),
    ) as client:
        await client.fetch_token(provider.token_url, code=code)
        response = await client.get(provider.userinfo_url, params=provider.extra_userinfo_params)
        response.raise_for_status()
        return response.json()
