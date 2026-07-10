import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _find_key_path(name: str) -> str:
    candidates = (
        Path("/app/keys") / name,
        Path(__file__).resolve().parents[2] / "auth-service" / "keys" / name,
    )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(candidates[-1])

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://analytics:analytics@localhost:5440/analytics_test"
)
os.environ.setdefault("EVENT_BUS_REDIS_URL", "redis://localhost:6390/1")
os.environ.setdefault("EVENT_BUS_ENABLED", "false")
os.environ.setdefault(
    "JWT_PUBLIC_KEY_PATH",
    _find_key_path("public.pem"),
)
os.environ.setdefault(
    "EXPORT_STORAGE_ROOT",
    str(Path(__file__).resolve().parents[1] / "storage" / "test-exports"),
)
os.environ.setdefault("EXPORT_WORKER_POLL_INTERVAL_SECONDS", "60")

import jwt
import shutil
import pytest
import pytest_asyncio
import redis.asyncio as redis_lib
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.db import Base

PRIVATE_KEY = (
    Path(_find_key_path("private.pem"))
).read_text()


def make_admin_token(
    user_id: uuid.UUID | None = None,
    *,
    role: str = "admin",
    ttl_seconds: int = 3600,
) -> str:
    now = int(time.time())
    claims = {
        "sub": str(user_id or uuid.uuid4()),
        "iss": settings.jwt_issuer,
        "role": role,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return jwt.encode(claims, PRIVATE_KEY, algorithm="RS256")


@pytest_asyncio.fixture
async def redis_client():
    client = redis_lib.from_url(settings.event_bus_redis_url, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def db_session():
    export_root = Path(settings.export_storage_root)
    shutil.rmtree(export_root, ignore_errors=True)
    export_root.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def api_client():
    from app.db import engine as app_engine

    export_root = Path(settings.export_storage_root)
    shutil.rmtree(export_root, ignore_errors=True)
    export_root.mkdir(parents=True, exist_ok=True)

    async with app_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        yield client

    await app_engine.dispose()


@pytest.fixture
def admin_auth_header():
    return {"Authorization": f"Bearer {make_admin_token()}"}
