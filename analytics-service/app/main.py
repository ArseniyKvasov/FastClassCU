import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.routers.analytics import router as analytics_router
from app.services import event_bus
from app.services.export_worker import run_worker
from fastclass_shared import configure_logging, install_metrics, install_request_middleware

configure_logging("analytics-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    consumer_task = None
    worker_task = asyncio.create_task(run_worker(stop_event))

    if settings.event_bus_enabled:
        consumer_task = asyncio.create_task(event_bus.run(stop_event))

    try:
        yield
    finally:
        stop_event.set()
        worker_task.cancel()
        await asyncio.gather(worker_task, return_exceptions=True)
        if consumer_task is not None:
            consumer_task.cancel()
            await asyncio.gather(consumer_task, return_exceptions=True)


app = FastAPI(title="Analytics Service", lifespan=lifespan)
install_request_middleware(app, service_name="analytics-service")
install_metrics(app, service_name="analytics-service")
app.include_router(analytics_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": exc.detail}
    headers = {}
    if exc.status_code == 429 and "retry_after_seconds" in detail:
        headers["Retry-After"] = str(detail["retry_after_seconds"])
    return JSONResponse(status_code=exc.status_code, content={"error": detail}, headers=headers)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    checks = {}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"

    if settings.event_bus_enabled:
        try:
            client = redis.from_url(settings.event_bus_redis_url, decode_responses=True)
            await client.ping()
            await client.aclose()
            checks["event_bus_redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["event_bus_redis"] = f"error: {exc}"
    else:
        checks["event_bus_redis"] = "disabled"

    try:
        export_root = Path(settings.export_storage_root)
        export_root.mkdir(parents=True, exist_ok=True)
        checks["export_storage"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["export_storage"] = f"error: {exc}"

    healthy = all(value in {"ok", "disabled"} for value in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"ready": healthy, "checks": checks},
    )
