import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.routers import classrooms, internal, membership, tokens
from app.services import event_bus
from app.ws import hub as ws_hub
from fastclass_shared import configure_logging, install_metrics, install_request_middleware

configure_logging("classroom-service")


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


app = FastAPI(title="Classroom Service", lifespan=lifespan)
install_request_middleware(app, service_name="classroom-service")
install_metrics(app, service_name="classroom-service")

app.include_router(classrooms.router)
app.include_router(membership.router)
app.include_router(internal.router)
app.include_router(tokens.router)
app.include_router(ws_hub.router)


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

    try:
        from app.redis_client import get_redis_client

        client = get_redis_client()
        await client.ping()
        await client.aclose()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc}"

    try:
        from redis.asyncio import from_url

        client = from_url(settings.rate_limit_redis_url, decode_responses=True)
        await client.ping()
        await client.aclose()
        checks["rate_limit_redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["rate_limit_redis"] = f"error: {exc}"

    if settings.event_bus_enabled:
        try:
            from redis.asyncio import from_url

            client = from_url(settings.event_bus_redis_url, decode_responses=True)
            await client.ping()
            await client.aclose()
            checks["event_bus_redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["event_bus_redis"] = f"error: {exc}"

    healthy = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503, content={"ready": healthy, "checks": checks}
    )
