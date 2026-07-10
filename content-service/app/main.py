import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import redis.asyncio as redis
from app.config import settings
from sqlalchemy import text

from app.db import engine
from app.routers import admin, collections, files, internal, lessons, quota, sections, tasks
from app.services.content import QuotaExceededError
from app.services import event_bus
from fastclass_shared import configure_logging, install_metrics, install_request_middleware

configure_logging("content-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    event_bus_task = None
    if settings.event_bus_enabled:
        event_bus_task = asyncio.create_task(event_bus.run(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        if event_bus_task is not None:
            event_bus_task.cancel()
            await asyncio.gather(event_bus_task, return_exceptions=True)


app = FastAPI(title="Content Service", lifespan=lifespan)
install_request_middleware(app, service_name="content-service")
install_metrics(app, service_name="content-service")

app.include_router(lessons.router)
app.include_router(sections.router)
app.include_router(tasks.router)
app.include_router(files.router)
app.include_router(quota.router)
app.include_router(admin.router)
app.include_router(collections.router)
app.include_router(internal.router)


# One error envelope for the whole API, instead of the old system's three
# incompatible shapes across different views.
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": exc.detail}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


@app.exception_handler(QuotaExceededError)
async def quota_exceeded_handler(request: Request, exc: QuotaExceededError) -> JSONResponse:
    return JSONResponse(
        status_code=409, content={"error": {"code": "quota_exceeded", "message": str(exc)}}
    )


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

    healthy = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503, content={"ready": healthy, "checks": checks}
    )
