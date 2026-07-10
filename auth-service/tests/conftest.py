import asyncio
import os
from pathlib import Path

import pytest

TEST_DIR = Path(__file__).resolve().parent
REPO_ROOT = TEST_DIR.parent

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://auth:auth@localhost:5433/auth_test"
)
os.environ.setdefault(
    "PROVIDERS_CONFIG_PATH", str(TEST_DIR / "fixtures" / "providers.test.yaml")
)
os.environ.setdefault("JWT_PRIVATE_KEY_PATH", str(REPO_ROOT / "keys" / "private.pem"))
os.environ.setdefault("JWT_PUBLIC_KEY_PATH", str(REPO_ROOT / "keys" / "public.pem"))
os.environ.setdefault("OAUTH_STATE_SECRET", "test-state-secret-at-least-32-bytes-long")
os.environ.setdefault(
    "SERVICE_CLIENTS_CONFIG_PATH", str(TEST_DIR / "fixtures" / "service_clients.test.yaml")
)
os.environ.setdefault("SERVICE_ACCESS_TOKEN_TTL_SECONDS", "300")
os.environ.setdefault("TESTPROVIDER_CLIENT_ID", "test-client-id")
os.environ.setdefault("TESTPROVIDER_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("ANSWERS_SERVICE_CLIENT_SECRET", "answers-secret")
os.environ.setdefault("AI_ASSISTANT_SERVICE_CLIENT_SECRET", "ai-secret")
os.environ.setdefault("COLLABORATION_SERVICE_CLIENT_SECRET", "collab-secret")

from app.db import Base, engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    async def _create():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        # Each TestClient context runs its own event loop; connections
        # pooled on this setup loop would otherwise be reused across loops
        # and asyncpg rejects that. Drop the pool so every test starts fresh.
        await engine.dispose()

    asyncio.run(_create())
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    # Must stay inside a single `with` block: TestClient opens one event
    # loop per context-manager scope, and the async SQLAlchemy engine's
    # pooled connections are bound to whichever loop created them - reusing
    # the client across separately-entered calls mixes loops and asyncpg
    # blows up with "attached to a different loop".
    with TestClient(app, follow_redirects=False) as c:
        yield c

    # Same cross-loop issue as above: drop pooled connections before the
    # next test spins up its own event loop.
    asyncio.run(engine.dispose())
