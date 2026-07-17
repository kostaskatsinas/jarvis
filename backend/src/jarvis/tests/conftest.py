import os

import pytest_asyncio

from jarvis.config import get_settings
from jarvis.core.checkpoint import close_checkpointer, open_checkpointer
from jarvis.db import session as db_session
from jarvis.db.models import Base


ADMIN_EMAIL = "admin@test.local"
ADMIN_PASSWORD = "correct-horse-battery"


@pytest_asyncio.fixture(autouse=True)
async def db(tmp_path):
    """Fresh file-backed SQLite per test; checkpointer falls back to in-memory."""
    url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    os.environ["JARVIS_DATABASE_URL"] = url
    os.environ["JARVIS_ADMIN_EMAIL"] = ADMIN_EMAIL
    os.environ["JARVIS_ADMIN_PASSWORD"] = ADMIN_PASSWORD
    os.environ["JARVIS_ENV"] = "dev"  # secure-cookie flag off: TestClient is plain http
    os.environ["JARVIS_SECRET_KEY"] = "test-secret-key-0123456789abcdef-0123456789abcdef"
    get_settings.cache_clear()

    from jarvis.api import auth

    auth._attempts.clear()  # login throttle state must not leak across tests
    db_session.configure(url)
    engine = db_session.get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def checkpointer():
    saver = await open_checkpointer()
    yield saver
    await close_checkpointer()
