from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://auth:auth@localhost:5432/auth"

    jwt_private_key_path: str = "keys/private.pem"
    jwt_public_key_path: str = "keys/public.pem"
    jwt_issuer: str = "auth-service"
    access_token_ttl_seconds: int = 900
    guest_token_ttl_seconds: int = 3600
    refresh_token_ttl_seconds: int = 2592000

    providers_config_path: str = "providers.yaml"
    public_base_url: str = "http://localhost:8001"

    # Signs the short-lived OAuth "state" param (CSRF + carries provider_key /
    # guest_session_id across the redirect). Separate from the RS256 user-token
    # keys on purpose: different blast radius, different rotation schedule.
    oauth_state_secret: str = "dev-insecure-change-me"
    oauth_state_ttl_seconds: int = 600

    service_access_token_ttl_seconds: int = 300
    service_clients_config_path: str = "service_clients.yaml"
    event_bus_redis_url: str = "redis://localhost:6390/0"
    event_bus_enabled: bool = True
    rate_limit_redis_url: str = "redis://localhost:6390/0"
    oauth_callback_rate_limit: int = 30
    oauth_callback_window_seconds: int = 60


settings = Settings()
