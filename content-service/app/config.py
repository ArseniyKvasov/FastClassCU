from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://content:content@localhost:5434/content"
    storage_root: str = "storage"
    teacher_storage_limit_bytes: int = 200 * 1024 * 1024
    jwt_public_key_path: str = "keys/public.pem"
    jwt_issuer: str = "auth-service"
    event_bus_redis_url: str = "redis://localhost:6390/0"
    event_bus_enabled: bool = True

    # Shared secret for service-to-service calls (e.g. Answers Service
    # fetching an answer key). Not a user JWT - a separate, narrower trust
    # boundary, same reasoning as Classroom Service's LiveKit/whiteboard
    # secrets being kept apart from the Auth Service signing key.
    internal_service_token: str = "dev-insecure-service-token"
    allow_legacy_internal_service_token: bool = True


settings = Settings()
