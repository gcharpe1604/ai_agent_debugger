"""The Alembic migrations and the SQLAlchemy models describe the same schema."""

import asyncio

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from agent_debugger_api.db import models  # noqa: F401  (registers the tables)
from agent_debugger_api.db.base import Base
from tests.postgres.harness import PostgresTestCase, alembic_config


class MigrationTests(PostgresTestCase):
    def run_sync(self, work):
        async def go():
            engine = create_async_engine(self.database_url, poolclass=NullPool)
            try:
                async with engine.connect() as connection:
                    return await connection.run_sync(work)
            finally:
                await engine.dispose()

        return asyncio.run(go())

    def test_migrated_schema_matches_the_models(self):
        diff = self.run_sync(lambda connection: compare_metadata(MigrationContext.configure(connection), Base.metadata))
        self.assertEqual(diff, [])

    def test_users_constraints_are_named(self):
        rows = self.sql(
            "SELECT conname FROM pg_constraint WHERE conrelid = 'users'::regclass AND contype = 'u' ORDER BY conname"
        )
        self.assertEqual([row[0] for row in rows], ["uq_users_email", "uq_users_key_hash", "uq_users_project_id"])

    def test_downgrade_drops_users_and_upgrade_restores_it(self):
        config = alembic_config(self.database_url)
        command.downgrade(config, "base")
        self.assertEqual(self.sql("SELECT to_regclass('users')")[0][0], None)
        command.upgrade(config, "head")
        self.assertEqual(self.sql("SELECT to_regclass('users')")[0][0], "users")
        self.assertEqual(self.sql("SELECT version_num FROM alembic_version")[0][0], "0001_create_users")

    def setUp(self):
        pass  # not PostgresTestCase.setUp: it truncates `users`, which the downgrade test drops for a moment
