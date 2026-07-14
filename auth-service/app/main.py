import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import redis.asyncio as redis
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.providers import PROVIDERS
from app.routers.auth import router as auth_router
from app.services import event_bus
from app.security import mint_token, verify_token
from fastclass_shared import configure_logging, install_metrics, install_request_middleware

configure_logging("auth-service")

logger = logging.getLogger("auth_service.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    event_bus_task = None

    # Fail fast on misconfiguration rather than 500ing on the first real
    # request: a bad key path or unreadable key is a deploy-time mistake,
    # not a runtime one.
    probe = mint_token(subject="startup-check", access_level="guest", ttl_seconds=5)
    verify_token(probe)

    if not PROVIDERS:
        logger.warning(
            "No OAuth providers loaded from providers.yaml - only guest "
            "sessions will be available until it's configured."
        )
    else:
        logger.info("Loaded OAuth providers: %s", ", ".join(PROVIDERS.keys()))

    if settings.event_bus_enabled:
        event_bus_task = asyncio.create_task(event_bus.run(stop_event))

    try:
        yield
    finally:
        stop_event.set()
        if event_bus_task is not None:
            event_bus_task.cancel()
            await asyncio.gather(event_bus_task, return_exceptions=True)


app = FastAPI(title="Auth Service", lifespan=lifespan)
install_request_middleware(app, service_name="auth-service")
install_metrics(app, service_name="auth-service")
app.include_router(auth_router, prefix="/auth", tags=["auth"])


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": exc.detail}
    headers = {}
    if exc.status_code == 429 and "retry_after_seconds" in detail:
        headers["Retry-After"] = str(detail["retry_after_seconds"])
    return JSONResponse(status_code=exc.status_code, content={"error": detail}, headers=headers)


@app.get("/health")
def health():
    """Liveness: is the process itself up. Deliberately has no dependency on
    the database, so a slow/unreachable DB doesn't get the container killed
    and restarted in a loop by an orchestrator's liveness probe."""
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    """Readiness: are this instance's actual dependencies reachable. Point
    your load balancer / k8s readiness probe here, not at /health."""
    checks = {}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - report whatever broke, not just DB errors
        checks["database"] = f"error: {exc}"

    try:
        probe = mint_token(subject="readiness-check", access_level="guest", ttl_seconds=5)
        verify_token(probe)
        checks["jwt_keys"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["jwt_keys"] = f"error: {exc}"

    if settings.event_bus_enabled:
        try:
            client = redis.from_url(
                settings.event_bus_redis_url,
                decode_responses=True,
                max_connections=2,
            )
            await client.ping()
            await client.aclose()
            checks["event_bus_redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["event_bus_redis"] = f"error: {exc}"

    try:
        client = redis.from_url(
            settings.rate_limit_redis_url,
            decode_responses=True,
            max_connections=2,
        )
        await client.ping()
        await client.aclose()
        checks["rate_limit_redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["rate_limit_redis"] = f"error: {exc}"

    healthy = all(v == "ok" for v in checks.values())
    status_code = 200 if healthy else 503
    return JSONResponse(status_code=status_code, content={"ready": healthy, "checks": checks})
