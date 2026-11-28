import os
from pathlib import Path
from app import metrics
import pytest

# لازم يتحدد قبل أي import للـ app
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["REDIS_URL"] = "redis://127.0.0.1:6379/15"
Path("test.db").unlink(missing_ok=True)

import httpx
import pytest_asyncio

import app.cache as cache_module
from app.circuit_breaker import breaker
from app.main import app
from app.redis_client import redis_client


@pytest_asyncio.fixture(scope="session", autouse=True)
async def lifespan():
    async with app.router.lifespan_context(app):
        yield


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture(autouse=True)
async def clean_state():
    metrics.reset()                 # أول سطر
    breaker._failures = 0
    breaker._opened_at = None
    breaker._probe_started_at = None
    cache_module._dirty = False
    await redis_client.flushdb()
    yield

@pytest_asyncio.fixture(scope="session", autouse=True)
async def require_redis():
    try:
        await redis_client.ping()
    except Exception as e:
        pytest.exit(
            f"Redis not reachable at {redis_client.connection_pool.connection_kwargs.get('host')}: {e}\n"
            "Run: docker compose up -d redis",
            returncode=2,
        )