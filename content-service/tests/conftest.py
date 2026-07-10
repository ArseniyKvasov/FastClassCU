import os
import uuid

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://content:content@localhost:5434/content_test"
)

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.db import Base


@pytest_asyncio.fixture
async def db_session(tmp_path, monkeypatch):
    """Fresh engine per test, disposed at teardown - pytest-asyncio gives each
    test its own event loop, and asyncpg connections can't be reused across
    loops, so sharing app.db.engine across tests causes cross-loop errors."""
    # Isolate file storage per test so file-leak assertions can't be
    # confused by blobs left over from a previous test run. Mutate the
    # existing singleton's `root` in place (rather than rebinding the module
    # attribute) since other modules did `from app.storage import storage`
    # and hold their own reference to the same object.
    import app.storage as storage_module

    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(storage_module.storage, "root", storage_dir)

    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    from sqlalchemy.ext.asyncio import async_sessionmaker

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def new_uuid():
    return uuid.uuid4


@pytest_asyncio.fixture
async def db_session_factory(tmp_path, monkeypatch):
    """Like db_session, but hands back a callable that opens a NEW session
    each time (all sharing one engine/connection pool) - needed to simulate
    two concurrent requests racing against the same database."""
    import app.storage as storage_module

    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(storage_module.storage, "root", storage_dir)

    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    from sqlalchemy.ext.asyncio import async_sessionmaker

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    yield SessionLocal

    await engine.dispose()


@pytest_asyncio.fixture
async def api_client(tmp_path, monkeypatch):
    """For tests that go through the real HTTP app (and therefore app.db's
    module-level engine, via the get_db dependency) rather than a service
    function directly. Must stay inside a single `with TestClient(...)`
    scope - see the identical note in auth-service's conftest for why."""
    import app.storage as storage_module
    from app.db import engine as app_engine

    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(storage_module.storage, "root", storage_dir)

    async with app_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    # Schema setup ran on THIS coroutine's loop, but TestClient's portal
    # drives the app on its own loop in a background thread - dispose now so
    # the pool starts empty and the portal opens fresh connections on its
    # own loop, instead of handing it a connection bound to this one.
    await app_engine.dispose()

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c

    await app_engine.dispose()
