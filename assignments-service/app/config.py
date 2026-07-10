from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://assignments:assignments@localhost:5436/assignments"
    redis_url: str = "redis://localhost:6381/0"

    jwt_public_key_path: str = "keys/public.pem"
    jwt_issuer: str = "auth-service"
    internal_service_token: str = "dev-insecure-service-token"
    allow_legacy_internal_service_token: bool = True
    event_bus_redis_url: str = "redis://localhost:6390/0"
    event_bus_enabled: bool = True

    ws_heartbeat_interval_seconds: int = 25
    ws_heartbeat_missed_limit: int = 3

    sweeper_interval_seconds: int = 30
    sweeper_batch_size: int = 500
    session_start_rate_limit: int = 20
    session_start_window_seconds: int = 300

    # Classroom-targeted assignments need a synchronous membership check at
    # session-start time (not everything between services is event-driven -
    # "can this student start this session right now" can't wait for an
    # eventually-consistent projection).
    classroom_service_base_url: str = "http://localhost:8004"


settings = Settings()
