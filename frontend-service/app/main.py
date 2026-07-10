from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastclass_shared import configure_logging, install_metrics, install_request_middleware

from app.config import settings
from app.routers import assignments, auth, classrooms, lessons

configure_logging("frontend-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Frontend Service", lifespan=lifespan)

install_request_middleware(app, service_name="frontend-service")
install_metrics(app, service_name="frontend-service")

app.include_router(auth.router)
app.include_router(lessons.router)
app.include_router(assignments.router)
app.include_router(classrooms.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": exc.detail}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    checks = {}
    try:
        async with httpx.AsyncClient(base_url=settings.auth_service_base_url, timeout=2.0) as client:
            response = await client.get("/auth/public-key")
        checks["auth_service"] = "ok" if response.status_code == 200 else f"error: {response.status_code}"
    except Exception as exc:  # noqa: BLE001
        checks["auth_service"] = f"error: {exc}"

    status_code = 200 if all(value == "ok" for value in checks.values()) else 503
    return JSONResponse(status_code=status_code, content=checks)


_static_dir = Path(settings.static_dir)
_assets_dir = _static_dir / "assets"
if _assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    index_file = _static_dir / "index.html"
    if not index_file.is_file():
        raise HTTPException(
            status_code=503,
            detail={"code": "spa_not_built", "message": "Run `npm run build` in web/ first"},
        )
    return FileResponse(index_file)
