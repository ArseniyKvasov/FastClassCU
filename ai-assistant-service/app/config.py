from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://ai:ai@localhost:5438/ai_assistant"

    jwt_public_key_path: str = "keys/public.pem"
    jwt_issuer: str = "auth-service"

    internal_service_token: str = "dev-insecure-service-token"
    content_service_base_url: str = "http://localhost:8003"
    content_service_token: str = "dev-insecure-service-token"
    auth_service_base_url: str = "http://localhost:8001"
    service_client_id: str = "ai-assistant-service"
    service_client_secret: str = ""
    content_service_scopes: tuple[str, ...] = (
        "content:lessons:read",
        "content:lesson-draft:write",
        "content:task-registry:read",
        "content:files:write",
    )

    worker_poll_interval_seconds: float = 2.0
    worker_batch_size: int = 4
    worker_max_attempts: int = 3
    event_bus_redis_url: str = "redis://localhost:6390/0"
    event_bus_enabled: bool = True
    rate_limit_redis_url: str = "redis://localhost:6390/0"
    generation_request_rate_limit: int = 20
    generation_request_window_seconds: int = 300

    ai_gateway_url: str | None = None
    ai_gateway_secret: str | None = None

    gemma_model: str = "gemma-4-27b-it"
    gemini_pdf_model: str = "gemini-2.5-flash"
    gigachat_model: str = "GigaChat-2"
    gemini_tts_model: str = "gemini-2.5-flash-preview-tts"

    gigachat_auth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    gigachat_api_url: str = "https://gigachat.devices.sberbank.ru/api/v1"
    gigachat_client_id: str | None = None
    gigachat_client_secret: str | None = None

    pollinations_base_url: str = "https://image.pollinations.ai"
    pollinations_api_key: str | None = None
    pollinations_image_model: str = "gptimage"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: str | None = None
    openrouter_image_model: str = "openai/gpt-image-2"
    flux_base_url: str | None = None
    flux_api_key: str | None = None
    flux_gateway_path: str = "pixazo/flux-1-schnell/v1/getData"

    use_mock_providers: bool = True
    recent_lessons_limit: int = 6
    max_context_lessons: int = 3
    max_feedback_items: int = 20
    default_lesson_language: str = "ru"
    default_audio_mime_type: str = "audio/wav"
    default_image_mime_type: str = "image/png"
    default_tts_voice: str = "aoede"
    default_image_quality: str = "low"

    generation_timeout_seconds: float = 120.0
    provider_timeout_seconds: float = 60.0

    supported_image_sizes: tuple[str, ...] = ("1024x1024", "1024x768", "768x1024")
    text_provider_chain: tuple[str, ...] = Field(default=("gemma", "gigachat"))
    pdf_provider_chain: tuple[str, ...] = Field(default=("gemini", "gigachat"))
    image_provider_chain: tuple[str, ...] = Field(default=("pollinations", "openrouter", "flux"))


settings = Settings()
