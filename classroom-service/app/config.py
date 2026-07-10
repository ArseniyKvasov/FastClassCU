from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://classroom:classroom@localhost:5435/classroom"
    redis_url: str = "redis://localhost:6380/0"

    jwt_public_key_path: str = "keys/public.pem"
    jwt_issuer: str = "auth-service"
    internal_service_token: str = "dev-insecure-service-token"
    allow_legacy_internal_service_token: bool = True
    event_bus_redis_url: str = "redis://localhost:6390/0"
    event_bus_enabled: bool = True
    rate_limit_redis_url: str = "redis://localhost:6380/0"

    join_password_min_length: int = 8
    join_attempts_per_ip_limit: int = 15
    join_attempts_per_ip_window_seconds: int = 3600
    join_attempts_global_per_classroom_limit: int = 50
    join_attempts_global_per_classroom_window_seconds: int = 3600
    join_lockout_seconds: int = 900

    ws_heartbeat_interval_seconds: int = 25
    ws_heartbeat_missed_limit: int = 3

    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    livekit_ws_url: str = "ws://localhost:7880"
    livekit_token_ttl_seconds: int = 3600

    whiteboard_jwt_secret: str = "dev-insecure-change-me"
    whiteboard_base_url: str = "http://localhost:9000"
    whiteboard_service_api_key: str = ""


settings = Settings()
