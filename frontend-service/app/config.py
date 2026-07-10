from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Service root, not process cwd - keeps relative defaults correct whether
# uvicorn is launched from this directory (Docker WORKDIR /app) or from
# elsewhere via --app-dir (e.g. a dev-server launcher).
_SERVICE_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_SERVICE_ROOT / ".env"), extra="ignore")

    auth_service_base_url: str = "http://localhost:8001"
    content_service_base_url: str = "http://localhost:8003"
    classroom_service_base_url: str = "http://localhost:8004"
    assignments_service_base_url: str = "http://localhost:8005"
    jwt_public_key_path: str = str(_SERVICE_ROOT / "keys" / "public.pem")
    jwt_issuer: str = "auth-service"

    # Cookie session - the SPA never touches raw tokens; the BFF holds them
    # in httpOnly cookies and attaches Authorization headers server-side when
    # proxying to backend services. Keeps tokens out of reach of any XSS in
    # the SPA bundle.
    session_cookie_name: str = "fc_session"
    refresh_cookie_name: str = "fc_refresh"
    cookie_domain: str | None = None
    cookie_secure: bool = False  # flip on behind HTTPS in every real deployment
    cookie_samesite: str = "lax"

    static_dir: str = str(_SERVICE_ROOT / "web" / "dist")

    event_bus_redis_url: str = "redis://localhost:6390/0"
    event_bus_enabled: bool = False

    cors_allow_origins: str = ""  # comma-separated; empty = same-origin only (dev server excluded)


settings = Settings()
