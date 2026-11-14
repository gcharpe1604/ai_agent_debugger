import unittest
from uuid import UUID

from tests.clickhouse.harness import ClickHouseTestCase, load_span_table_ddl

PROJECT = UUID("00000000-0000-4000-8000-000000000001")
TRACE = "1" * 32
SPAN = "a" * 16


class LoadDdlTests(unittest.TestCase):
    def test_retargets_the_documented_table(self):
        ddl = load_span_table_ddl("scratch_x")
        self.assertIn("CREATE TABLE IF NOT EXISTS scratch_x.telemetry_spans", ddl)
        self.assertNotIn("telemetry.telemetry_spans", ddl)
        self.assertIn("ORDER BY (project_id, trace_id, span_id, content_hash)", ddl)


class HarnessTests(ClickHouseTestCase):
    def test_scratch_database_has_the_span_table(self):
        tables = self.client.query(f"SHOW TABLES FROM {self.database}").result_rows
        self.assertEqual(tables, [("telemetry_spans",)])

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
