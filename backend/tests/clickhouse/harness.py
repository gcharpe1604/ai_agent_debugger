"""Test harness for the ClickHouse writer: one scratch database per test class.

The database and table are created by trace_writer.schema.ensure_schema, from
the same schema.sql the writer applies at startup, so tests always run against
the production schema. Nothing here touches the `telemetry` database.

Connection settings come from the environment, with the compose defaults from
.env.example: CLICKHOUSE_HOST, CLICKHOUSE_PORT (HTTP), CLICKHOUSE_USER,
CLICKHOUSE_PASSWORD. If the server is unreachable the whole class is skipped,
unless CLICKHOUSE_REQUIRED=1 (set in CI), which makes it an error.
"""
import os
import unittest
import uuid

import clickhouse_connect
from agent_debugger_api.trace_writer.schema import TABLE, ensure_schema


def clickhouse_client():
    """A client for the test server, or SkipTest / RuntimeError (CLICKHOUSE_REQUIRED=1)."""
    host = os.environ.get("CLICKHOUSE_HOST", "localhost")
    port = int(os.environ.get("CLICKHOUSE_PORT", "8123"))
    try:
        client = clickhouse_connect.get_client(
            host=host,
            port=port,
            username=os.environ.get("CLICKHOUSE_USER", "agentdbg"),
            password=os.environ.get("CLICKHOUSE_PASSWORD", "agentdbg"),
            connect_timeout=3,
        )
        client.command("SELECT 1")
        return client
    except Exception as exc:  # any connection or auth failure means "no server for tests"
        if os.environ.get("CLICKHOUSE_REQUIRED") == "1":  # CI: a missing server is an error, not a skip
            raise RuntimeError(f"ClickHouse not reachable at {host}:{port}") from exc
        raise unittest.SkipTest(
            f"ClickHouse not reachable at {host}:{port} ({type(exc).__name__}). "
            "Start it with `docker compose up -d clickhouse` to run these tests."
        ) from None


class ClickHouseTestCase(unittest.TestCase):
    """Creates `cls.database` with the span table (schema.sql) before the class, drops it after."""

    client = None
    database = ""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = clickhouse_client()
        cls.database = f"scratch_{cls.__name__.lower()}_{uuid.uuid4().hex[:8]}"
        # Registered before the schema is created, so a DDL failure still drops the database.
        cls.addClassCleanup(cls._drop_database)
        ensure_schema(cls.client, cls.database)

    @classmethod
    def _drop_database(cls):
        try:
            cls.client.command(f"DROP DATABASE IF EXISTS {cls.database}")
        finally:
            cls.client.close()

    @property
    def table(self) -> str:
        return f"{self.database}.{TABLE}"
