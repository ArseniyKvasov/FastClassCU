import os
import time
import uuid

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://classroom:classroom@localhost:5435/classroom_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/1")

import jwt
import pytest
import pytest_asyncio
import redis.asyncio as redis_lib
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.db import Base

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
_PRIVATE_KEY = (REPO_ROOT / "keys" / "dev_private.pem").read_text()


def make_token(
    user_id: uuid.UUID | None = None, *, access_level: str = "full", ttl_seconds: int = 3600
) -> str:
    """Signs a token the same shape Auth Service would issue, using the dev
    keypair whose public half lives at keys/public.pem (what this service's
    JWT_PUBLIC_KEY_PATH points at) - proves verification works against a real
    RS256 pair without needing a running Auth Service."""
    now = int(time.time())
    claims = {
        "sub": str(user_id or uuid.uuid4()),
        "iss": settings.jwt_issuer,
        "access_level": access_level,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return jwt.encode(claims, _PRIVATE_KEY, algorithm="RS256")


@pytest_asyncio.fixture
async def redis_client():
    client = redis_lib.from_url(settings.redis_url, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def api_client(redis_client, monkeypatch):
    """Real HTTP app, real Postgres, real Redis. Must stay inside a single
    `with TestClient(...)` scope - see auth-service/content-service conftest
    for why (TestClient's portal runs the app on its own event loop)."""
    from app.db import engine as app_engine
    import app.redis_client as app_redis
    import redis.asyncio as redis_lib

    async with app_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await app_engine.dispose()

    # The module-level redis_pool is a singleton the app's get_redis
    # dependency shares across every request. Trying to .disconnect() a pool
    # created on a PREVIOUS test's (now-closed) event loop fails outright -
    # asyncio won't let you touch transport objects bound to a dead loop.
    # Simplest fix: give this test a brand new pool instead of reusing/
    # disconnecting the old one; nothing ever touches the old loop.
    fresh_pool = redis_lib.ConnectionPool.from_url(settings.redis_url, decode_responses=True)
    monkeypatch.setattr(app_redis, "redis_pool", fresh_pool)

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c

    await app_engine.dispose()


@pytest.fixture
def new_uuid():
    return uuid.uuid4
