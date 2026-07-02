import pytest
from httpx import ASGITransport, AsyncClient

from api.db import engine
from api.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="session", autouse=True)
async def _dispose_engine():
    yield
    await engine.dispose()
