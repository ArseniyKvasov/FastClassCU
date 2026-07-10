from pydantic import BaseModel


class ProviderOut(BaseModel):
    key: str
    display_name: str


class GuestTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    guest_session_id: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class PublicKeyOut(BaseModel):
    algorithm: str = "RS256"
    public_key: str


class ServiceTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
