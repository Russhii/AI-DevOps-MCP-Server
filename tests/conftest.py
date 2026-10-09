import os
import tempfile

# Must be set before any `app` import (the DB engine is created at import time).
_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_db.name}"
os.environ["REQUIRE_AUTH"] = "false"
os.environ["API_KEYS"] = "admin:admin-key:read+write+destructive,writer:writer-key:read+write,viewer:viewer-key:read"
os.environ["GITHUB_TOKEN"] = ""

import pytest  # noqa: E402
from mcp import Client  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.server import create_server  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    import app.models.task  # noqa: F401

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


class PerCallClient:
    """In-memory MCP client that opens a fresh session per call.

    Avoids holding an anyio cancel scope across pytest fixture setup/teardown tasks.
    """

    def __init__(self):
        self.server = create_server()

    async def _with(self, method, *args, **kwargs):
        async with Client(self.server) as c:
            return await getattr(c, method)(*args, **kwargs)

    def __getattr__(self, method):
        async def call(*args, **kwargs):
            return await self._with(method, *args, **kwargs)

        return call


@pytest.fixture
def client():
    return PerCallClient()
