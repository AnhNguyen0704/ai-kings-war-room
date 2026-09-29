"""Test environment: isolated SQLite DB, zero mock delays, fast debate rounds.

Env vars are set BEFORE any app import so engine/settings bind to the test DB.
"""
import os
import pathlib

_BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
_TEST_DB = _BACKEND_DIR / "data" / "test.db"

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB.as_posix()}"
os.environ["MOCK_THINK_DELAY"] = "0"
os.environ["MOCK_TOKEN_DELAY"] = "0"
os.environ["DISCUSSION_ROUNDS"] = "1"
os.environ["OPENAI_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""
os.environ["XAI_API_KEY"] = ""
os.environ["MOONSHOT_API_KEY"] = ""

if _TEST_DB.exists():
    _TEST_DB.unlink()

import asyncio  # noqa: E402

import pytest  # noqa: E402
import sqlalchemy as sa  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db.database import async_session_factory  # noqa: E402
from app.models.entities import (  # noqa: E402
    Agent,
    Debate,
    Decision,
    EventLog,
    MemoryItem,
    Message,
    Room,
    RoomAgent,
    Task,
    User,
    Vote,
)


@pytest.fixture(scope="session")
async def app_setup():
    from app.main import setup_for_tests

    app = await setup_for_tests()
    yield app


@pytest.fixture()
async def client(app_setup):
    async with AsyncClient(transport=ASGITransport(app=app_setup), base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
async def _clean_between_tests(app_setup):
    """Wipe all data after each test and re-seed defaults, so tests are independent."""
    yield
    from app.orchestration.registry import reset_all
    from app.db.seed import seed_defaults

    await asyncio.sleep(0.05)  # let fire-and-forget event-persist tasks settle
    await reset_all()
    async with async_session_factory() as session:
        for table in (
            EventLog,
            MemoryItem,
            Decision,
            Vote,
            Message,
            Task,
            Debate,
            RoomAgent,
            Room,
            Agent,
            User,
        ):
            await session.execute(sa.delete(table))
        await session.commit()
    await seed_defaults()


@pytest.fixture()
async def seeded_room_id(client) -> str:
    resp = await client.get("/api/rooms")
    return resp.json()["rooms"][0]["id"]
