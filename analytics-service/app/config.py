from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://analytics:analytics@localhost:5440/analytics"
    jwt_public_key_path: str = "keys/public.pem"
    jwt_issuer: str = "auth-service"

    event_bus_redis_url: str = "redis://localhost:6390/0"
    event_bus_enabled: bool = True

    export_storage_root: str = "storage/exports"
    export_worker_poll_interval_seconds: float = 2.0
    export_max_rows: int = 50_000


settings = Settings()
