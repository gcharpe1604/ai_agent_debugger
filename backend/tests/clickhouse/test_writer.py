from agent_debugger_api.trace_writer.clickhouse_store import ClickHouseTraceStore
from tests.clickhouse.harness import ClickHouseTestCase
from tests.contracts.factories import make_span


class WriterTests(ClickHouseTestCase):
    def setUp(self):
        self.store = ClickHouseTraceStore(self.client, table=self.table)

    def test_duplicate_is_one_logical_row(self):
        span = make_span()
        self.store.insert_spans([span])
        self.store.insert_spans([span])         # redelivery = second part
        rows = self.store.get_trace(span.project_id, span.trace_id)
        self.assertEqual(len(rows), 1)

    def test_received_at_is_sorted_in_ms(self):
        span = make_span(received_at=1_700_000_000_123_456_789)
        self.store.insert_spans([span])
        row = self.store.get_trace(span.project_id, span.trace_id)[0]
        self.assertEqual(row["received_at"], 1_700_000_000_123) 
