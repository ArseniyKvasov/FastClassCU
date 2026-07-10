from __future__ import annotations

import asyncio
import secrets
import time
from pathlib import Path
from typing import Any

import httpx
import jwt

from fastclass_shared.context import bind_actor
from fastclass_shared.http import propagate_headers


class ServiceAuthError(Exception):
    pass


def _read_public_key(path: str) -> str:
    return Path(path).read_text()


def _scopes_from_claims(claims: dict[str, Any]) -> set[str]:
    raw = claims.get("scope") or ""
    if isinstance(raw, str):
        return {item for item in raw.split() if item}
    if isinstance(raw, list):
        return {str(item) for item in raw if str(item)}
    return set()


def verify_service_jwt(
    token: str,
    *,
    public_key_path: str,
    issuer: str,
    required_scopes: set[str] | None = None,
) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            _read_public_key(public_key_path),
            algorithms=["RS256"],
            issuer=issuer,
        )
    except jwt.PyJWTError as exc:
        raise ServiceAuthError(f"invalid_service_jwt:{exc}") from exc

    if claims.get("token_use") != "service":
        raise ServiceAuthError("invalid_service_jwt_use")

    scopes = _scopes_from_claims(claims)
    if required_scopes and not required_scopes.issubset(scopes):
        raise ServiceAuthError("insufficient_service_scope")

    bind_actor(service=str(claims.get("sub") or "unknown-service"))
    return claims


def verify_legacy_service_token(
    token: str | None,
    *,
    expected_token: str,
) -> None:
    if not token or not secrets.compare_digest(token, expected_token):
        raise ServiceAuthError("invalid_legacy_service_token")
    bind_actor(service="legacy-service-token")


def authenticate_service_request(
    *,
    authorization: str | None,
    x_service_token: str | None,
    public_key_path: str,
    issuer: str,
    required_scopes: set[str] | None = None,
    allow_legacy_token: bool,
    legacy_token: str | None,
) -> dict[str, Any] | None:
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        return verify_service_jwt(
            token,
            public_key_path=public_key_path,
            issuer=issuer,
            required_scopes=required_scopes,
        )

    if allow_legacy_token and legacy_token:
        verify_legacy_service_token(x_service_token, expected_token=legacy_token)
        return None

    raise ServiceAuthError("missing_service_credentials")


class ServiceTokenProvider:
    def __init__(
        self,
        *,
        auth_base_url: str,
        client_id: str,
        client_secret: str,
        scopes: tuple[str, ...],
        enabled: bool,
    ) -> None:
        self.auth_base_url = auth_base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = scopes
        self.enabled = enabled and bool(client_id and client_secret and auth_base_url)
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    async def get_authorization_header(self) -> dict[str, str]:
        if not self.enabled:
            return {}
        token = await self._get_token()
        return {"Authorization": f"Bearer {token}"}

    async def _get_token(self) -> str:
        now = time.time()
        if self._token and now < self._expires_at - 30:
            return self._token

        async with self._lock:
            now = time.time()
            if self._token and now < self._expires_at - 30:
                return self._token

            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(
                    f"{self.auth_base_url}/auth/service-token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "scope": " ".join(self.scopes),
                    },
                    headers=propagate_headers({"Content-Type": "application/x-www-form-urlencoded"}),
                )
            response.raise_for_status()
            payload = response.json()
            self._token = payload["access_token"]
            self._expires_at = now + int(payload.get("expires_in") or 60)
            return self._token
