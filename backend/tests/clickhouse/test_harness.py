import unittest
from uuid import UUID

from agent_debugger_api.trace_writer.schema import ensure_schema, schema_statements

from tests.clickhouse.harness import ClickHouseTestCase

PROJECT = UUID("00000000-0000-4000-8000-000000000001")
TRACE = "1" * 32
SPAN = "a" * 16


class SchemaStatementsTests(unittest.TestCase):
    def test_database_then_table_retargeted_without_comments(self):
        create_db, create_table = schema_statements("scratch_x")
        self.assertEqual(create_db, "CREATE DATABASE IF NOT EXISTS scratch_x")
        self.assertTrue(create_table.startswith("CREATE TABLE IF NOT EXISTS scratch_x.telemetry_spans"))
        self.assertTrue(create_table.endswith("ORDER BY (project_id, trace_id, span_id, content_hash)"))
        self.assertNotIn("--", create_table)
        self.assertNotIn("{database}", create_table)

    def test_rejects_a_database_name_that_is_not_an_identifier(self):
        for name in ("", "telemetry; DROP TABLE x", "a.b", "1abc", "a-b"):
            with self.subTest(name), self.assertRaises(ValueError):
                schema_statements(name)


class HarnessTests(ClickHouseTestCase):
    def test_scratch_database_has_the_span_table(self):
        tables = self.client.query(f"SHOW TABLES FROM {self.database}").result_rows
        self.assertEqual(tables, [("telemetry_spans",)])

    def test_ensure_schema_is_idempotent(self):
        ensure_schema(self.client, self.database)  # second run, as on every writer start
        self.assertEqual(self.client.query(f"SHOW TABLES FROM {self.database}").result_rows, [("telemetry_spans",)])

    def test_insert_and_select_one_row(self):
        self.client.insert(
            self.table,
            [[PROJECT, TRACE, SPAN, "f" * 64, "svc", "run", "root"]],
            column_names=["project_id", "trace_id", "span_id", "content_hash", "service_name", "operation_type", "span_name"],
        )
        rows = self.client.query(
            f"SELECT project_id, trace_id, span_id, span_name, parent_span_id, cost FROM {self.table}"
        ).result_rows
        self.assertEqual(len(rows), 1)
        project_id, trace_id, span_id, span_name, parent, cost = rows[0]
        self.assertEqual(project_id, PROJECT)
        self.assertEqual(trace_id.decode() if isinstance(trace_id, bytes) else trace_id, TRACE)
        self.assertEqual(span_id.decode() if isinstance(span_id, bytes) else span_id, SPAN)
        self.assertEqual(span_name, "root")
        self.assertIsNone(parent)
        self.assertIsNone(cost)
