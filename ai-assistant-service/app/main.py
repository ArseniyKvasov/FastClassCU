import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import get_engine
from app.routers import generations, memory
from app.config import settings
from app.services import event_bus
from app.services.worker import run_worker
from fastclass_shared import configure_logging, install_metrics, install_request_middleware

configure_logging("ai-assistant-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    stop_event.clear()
    worker_task = asyncio.create_task(run_worker(stop_event))
    relay_task = None
    if settings.event_bus_enabled:
        relay_task = asyncio.create_task(event_bus.run(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        await worker_task
        if relay_task is not None:
            await relay_task


app = FastAPI(title="AI Assistant Service", lifespan=lifespan)
install_request_middleware(app, service_name="ai-assistant-service")
install_metrics(app, service_name="ai-assistant-service")

app.include_router(generations.router)
app.include_router(memory.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": exc.detail}
    headers = {}
    if exc.status_code == 429 and "retry_after_seconds" in detail:
        headers["Retry-After"] = str(detail["retry_after_seconds"])
    return JSONResponse(status_code=exc.status_code, content={"error": detail}, headers=headers)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=400, content={"error": {"code": "invalid_request", "message": str(exc)}}
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    checks = {}
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"
    try:
        if Path(settings.jwt_public_key_path).exists():
            checks["jwt_public_key"] = "ok"
        else:
            checks["jwt_public_key"] = "missing"
    except Exception as exc:  # noqa: BLE001
        checks["jwt_public_key"] = f"error: {exc}"
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
    else:
        checks["event_bus_redis"] = "disabled"

    healthy = all(value in {"ok", "disabled"} for value in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"ready": healthy, "checks": checks},
    )
