from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://answers:answers@localhost:5437/answers"
    redis_url: str = "redis://localhost:6382/0"

    jwt_public_key_path: str = "keys/public.pem"
    jwt_issuer: str = "auth-service"

    storage_root: str = "storage"

    content_service_base_url: str = "http://localhost:8003"
    content_service_token: str = "dev-insecure-service-token"
    auth_service_base_url: str = "http://localhost:8001"
    service_client_id: str = "answers-service"
    service_client_secret: str = ""
    content_service_scopes: tuple[str, ...] = ("content:answer-key:read",)

    classroom_service_base_url: str = "http://localhost:8004"
    assignments_service_base_url: str = "http://localhost:8005"

    student_answer_limit_bytes: int = 15 * 1024 * 1024
    event_bus_redis_url: str = "redis://localhost:6390/0"
    event_bus_enabled: bool = True
    answer_submit_rate_limit: int = 120
    answer_submit_window_seconds: int = 60

    # Incoming service-to-service auth - Collaboration Service (snapshots)
    # and the Content Service event relay (cache invalidation) call these
    # internal endpoints with this token, never a user JWT.
    internal_service_token: str = "dev-insecure-service-token"
    allow_legacy_internal_service_token: bool = True


settings = Settings()
