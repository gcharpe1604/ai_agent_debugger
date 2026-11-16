"""Create the ClickHouse database and `telemetry_spans` table if they are missing.

The DDL is schema.sql next to this file: the writer runs it at startup and the
test harness runs the same file against scratch databases, so tests and
production cannot drift apart.
"""

import re
from importlib.resources import files

TABLE = "telemetry_spans"
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_COMMENT = re.compile(r"--[^\n]*")


def schema_statements(database: str) -> list[str]:
    """The statements in schema.sql for `database`, comments removed, in order."""
    # The name is put into the SQL text, so only plain identifiers are allowed.
    if not _IDENTIFIER.match(database):
        raise ValueError(f"invalid ClickHouse database name: {database!r}")
    sql = files(__package__).joinpath("schema.sql").read_text(encoding="utf-8")
    sql = _COMMENT.sub("", sql).replace("{database}", database)
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def ensure_schema(client, database: str) -> None:
    """Run CREATE DATABASE / CREATE TABLE IF NOT EXISTS. Safe to call on every start."""
    for statement in schema_statements(database):
        client.command(statement)
