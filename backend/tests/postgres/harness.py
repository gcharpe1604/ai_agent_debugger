"""Test harness for PostgreSQL: one scratch database per test class, migrated with Alembic.

The scratch database is created on the server of DATABASE_URL (environment,
else the repo-root .env, else the compose default) and brought to `head` by
the real migrations in backend/migrations, so tests run against the schema a
deployment gets. The database in DATABASE_URL itself is never changed.

If the server is unreachable the whole class is skipped, unless
POSTGRES_REQUIRED=1 (set in CI), which makes it an error.

Engines use NullPool: TestClient runs each request on its own event loop, and
an asyncpg connection cannot move between loops.
"""

import asyncio
import os
import unittest
import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

BACKEND = Path(__file__).resolve().parents[2]
COMPOSE_URL = "postgresql+asyncpg://agent_debugger:agent_debugger@localhost:5433/agent_debugger"


def server_url() -> str:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    try:
        from agent_debugger_api.config import get_settings

        return get_settings().database_url
    except Exception:  # no .env: the compose default
        return COMPOSE_URL


def alembic_config(url: str) -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.attributes["database_url"] = url
    config.attributes["configure_logger"] = False  # keep the test runner's logging as it is
    return config


async def _execute(url: str, sql: str) -> None:
    # AUTOCOMMIT: CREATE / DROP DATABASE cannot run inside a transaction.
    engine = create_async_engine(url, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(text(sql))
    finally:
        await engine.dispose()


class PostgresTestCase(unittest.TestCase):
    """`cls.database_url`, `cls.sessions` on a migrated scratch database; `users` emptied before each test."""

    database_url = ""
    sessions: async_sessionmaker[AsyncSession]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        server = make_url(server_url())
        admin = server.render_as_string(hide_password=False)
        try:
            asyncio.run(_execute(admin, "SELECT 1"))
        except Exception as exc:  # any connection or auth failure means "no server for tests"
            where = f"{server.host}:{server.port}"
            if os.environ.get("POSTGRES_REQUIRED") == "1":  # CI: a missing server is an error, not a skip
                raise RuntimeError(f"PostgreSQL not reachable at {where}") from exc
            raise unittest.SkipTest(
                f"PostgreSQL not reachable at {where} ({type(exc).__name__}). "
                "Start it with `docker compose up -d postgres` to run these tests."
            ) from None
        name = f"scratch_{cls.__name__.lower()}_{uuid.uuid4().hex[:8]}"
        asyncio.run(_execute(admin, f'CREATE DATABASE "{name}"'))
        # Registered before migrating, so a failed migration still drops the database.
        cls.addClassCleanup(lambda: asyncio.run(_execute(admin, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')))
        cls.database_url = server.set(database=name).render_as_string(hide_password=False)
        command.upgrade(alembic_config(cls.database_url), "head")
        cls.sessions = async_sessionmaker(
            create_async_engine(cls.database_url, poolclass=NullPool), expire_on_commit=False
        )

    def setUp(self):
        super().setUp()
        self.sql("TRUNCATE users")

    def run_db(self, work):
        """`await work(session)` on a new session and event loop; returns its result."""

        async def go():
            async with self.sessions() as session:
                return await work(session)

        return asyncio.run(go())

    def sql(self, statement: str, **params):
        async def work(session):
            result = await session.execute(text(statement), params)
            rows = result.all() if result.returns_rows else None
            await session.commit()
            return rows

        return self.run_db(work)
