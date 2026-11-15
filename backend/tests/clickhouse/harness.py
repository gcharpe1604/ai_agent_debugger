"""Test harness for the ClickHouse writer: one scratch database per test class.

The table definition is read from the §2 DDL in
docs/proposals/clickhouse-span-record.md, so tests always run against the
documented schema. Nothing here touches the `telemetry` database.

Connection settings come from the environment, with the compose defaults from
.env.example: CLICKHOUSE_HOST, CLICKHOUSE_PORT (HTTP), CLICKHOUSE_USER,
CLICKHOUSE_PASSWORD. If the server is unreachable the whole class is skipped.
"""
import os
import re
import unittest
import uuid
from pathlib import Path

import clickhouse_connect

REPO_ROOT = Path(__file__).resolve().parents[3]
SPAN_RECORD_DOC = REPO_ROOT / "docs" / "proposals" / "clickhouse-span-record.md"
DOC_TABLE = "telemetry.telemetry_spans"
TABLE = "telemetry_spans"


def load_span_table_ddl(database: str) -> str:
    """Return the §2 CREATE TABLE statement, retargeted at `database`."""
    text = SPAN_RECORD_DOC.read_text(encoding="utf-8")
    section = re.search(r"^## 2\..*?(?=^## 3\.)", text, re.S | re.M)
    if section is None:
        raise RuntimeError(f"§2 not found in {SPAN_RECORD_DOC}")
    block = re.search(r"```sql\n(.*?)```", section.group(0), re.S)
    if block is None:
        raise RuntimeError(f"No sql block in §2 of {SPAN_RECORD_DOC}")
    ddl = block.group(1).strip().rstrip(";")
    if ddl.count(DOC_TABLE) != 1:
        raise RuntimeError(f"Expected exactly one {DOC_TABLE} in the §2 DDL")
    return ddl.replace(DOC_TABLE, f"{database}.{TABLE}")


class ClickHouseTestCase(unittest.TestCase):
    """Creates `cls.database` with the §2 table before the class, drops it after."""

    client = None
    database = ""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        host = os.environ.get("CLICKHOUSE_HOST", "localhost")
        port = int(os.environ.get("CLICKHOUSE_PORT", "8123"))
        try:
            cls.client = clickhouse_connect.get_client(
                host=host,
                port=port,
                username=os.environ.get("CLICKHOUSE_USER", "agentdbg"),
                password=os.environ.get("CLICKHOUSE_PASSWORD", "agentdbg"),
                connect_timeout=3,
            )
            cls.client.command("SELECT 1")
        except Exception as exc:  # any connection or auth failure means "no server for tests"
            raise unittest.SkipTest(
                f"ClickHouse not reachable at {host}:{port} ({type(exc).__name__}). "
                "Start it with `docker compose up -d clickhouse` to run these tests."
            ) from None

        cls.database = f"scratch_{cls.__name__.lower()}_{uuid.uuid4().hex[:8]}"
        cls.client.command(f"CREATE DATABASE {cls.database}")
        # Registered before the table is created, so a DDL failure still drops the database.
        cls.addClassCleanup(cls._drop_database)
        cls.client.command(load_span_table_ddl(cls.database))

    @classmethod
    def _drop_database(cls):
        try:
            cls.client.command(f"DROP DATABASE IF EXISTS {cls.database}")
        finally:
            cls.client.close()

    @property
    def table(self) -> str:
        return f"{self.database}.{TABLE}"
