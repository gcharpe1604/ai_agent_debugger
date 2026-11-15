"""Round-trip every telemetry_spans column through clickhouse-connect.

No writer code: rows are built here from SpanRecord with the value shapes that
were checked against ClickHouse 26.8 and clickhouse-connect 1.12:

- DateTime64(n): insert an int of raw ticks (ns for n=9, ms for n=3). Read with
  query_formats {"DateTime64": "int"}; the default read gives datetime, which
  keeps only microseconds. An int is not converted: ns into a DateTime64(3)
  column is stored as ms ticks, a date far in the future, with no error.
- Decimal(18, 9): insert Decimal(cost_string). Reads come back as Decimal with
  exponent -9 ("0.00125" -> Decimal("0.001250000")): equal as numbers, not as text.
- Enum8: insert the string value. An unknown string is stored silently as
  value 0 ('UNSET' for status_code, NULL on read for the payload states).
- FixedString(n): insert str. Read with query_formats {"FixedString": "string"};
  the default read gives bytes. Shorter values are NUL-padded silently.
- UUID: uuid.UUID in and out. Nullable: None in and out.
- Map(String, String): dict. Array(Tuple(...)): list of tuples (dicts also work);
  read back as a list of dicts keyed by the tuple element names.
"""

import unittest
from decimal import Decimal

from agent_debugger_api.contracts import SpanRecord
from agent_debugger_api.trace_writer.content_hash import content_hash
from tests.clickhouse.harness import ClickHouseTestCase
from tests.contracts.factories import make_span

READ_FORMATS = {"DateTime64": "int", "FixedString": "string"}
NS_PER_MS = 1_000_000
PERSISTED_AT_MS = 1_700_000_002_000  # supplied explicitly so the read is exact

# Every column in the §2 DDL. The test fails if the table gains or loses one.
DDL_COLUMNS = {
    "project_id", "trace_id", "span_id", "parent_span_id", "content_hash",
    "service_name", "operation_type", "span_name", "display_label", "execution_mode",
    "graph_node_id", "graph_node_parent_id", "status_code", "status_description",
    "error_type", "started_at", "ended_at", "duration_ns", "attempt", "retry_of_span_id",
    "model", "provider", "input_tokens", "output_tokens", "total_tokens", "cost",
    "input_state", "input_payload", "output_state", "output_payload", "error_state",
    "error_payload", "attributes", "events", "links", "protocol_version", "received_at",
    "persisted_at", "kafka_partition", "kafka_offset",
}


def insert_row(span: SpanRecord, partition: int, offset: int) -> dict:
    """Column -> value in the shape clickhouse-connect stores exactly."""
    return {
        "project_id": span.project_id,
        "trace_id": span.trace_id,
        "span_id": span.span_id,
        "parent_span_id": span.parent_span_id,
        "content_hash": content_hash(span),
        "service_name": span.service_name,
        "operation_type": span.operation_type,
        "span_name": span.span_name,
        "display_label": span.display_label,
        "execution_mode": span.execution_mode,
        "graph_node_id": span.graph_node_id,
        "graph_node_parent_id": span.graph_node_parent_id,
        "status_code": span.status_code.value,
        "status_description": span.status_description,
        "error_type": span.error_type,
        "started_at": span.started_at,
        "ended_at": span.ended_at,
        "duration_ns": span.ended_at - span.started_at,
        "attempt": span.attempt,
        "retry_of_span_id": span.retry_of_span_id,
        "model": span.model,
        "provider": span.provider,
        "input_tokens": span.input_tokens,
        "output_tokens": span.output_tokens,
        "total_tokens": span.total_tokens,
        "cost": None if span.cost is None else Decimal(span.cost),
        "input_state": span.input_state.value,
        "input_payload": span.input_payload,
        "output_state": span.output_state.value,
        "output_payload": span.output_payload,
        "error_state": span.error_state.value,
        "error_payload": span.error_payload,
        "attributes": dict(span.attributes),
        "events": [(e.name, e.time, dict(e.attributes)) for e in span.events],
        "links": [(link.trace_id, link.span_id, link.relation) for link in span.links],
        "protocol_version": span.protocol_version,
        "received_at": span.received_at // NS_PER_MS,  # DateTime64(3): ms ticks, truncated
        "persisted_at": PERSISTED_AT_MS,
        "kafka_partition": partition,
        "kafka_offset": offset,
    }


def expected_read(span: SpanRecord, partition: int, offset: int) -> dict:
    """What SELECT * returns with READ_FORMATS: tuples come back as dicts."""
    row = insert_row(span, partition, offset)
    row["events"] = [{"name": e.name, "time": e.time, "attributes": dict(e.attributes)} for e in span.events]
    row["links"] = [{"trace_id": link.trace_id, "span_id": link.span_id, "relation": link.relation} for link in span.links]
    return row


class TypeRoundTripTests(ClickHouseTestCase):
    def roundtrip(self, span: SpanRecord, partition: int, offset: int) -> dict:
        row = insert_row(span, partition, offset)
        self.assertEqual(set(row), DDL_COLUMNS)
        self.client.insert(self.table, [list(row.values())], column_names=list(row))
        result = self.client.query(
            f"SELECT * FROM {self.table} WHERE span_id = %(span_id)s",
            parameters={"span_id": span.span_id},
            query_formats=READ_FORMATS,
        )
        self.assertEqual(set(result.column_names), DDL_COLUMNS)
        [read] = list(result.named_results())
        self.assertEqual(read, expected_read(span, partition, offset))
        return read

    def test_minimal_span(self):
        span = make_span(span_id="1" * 16)
        read = self.roundtrip(span, partition=0, offset=0)
        for column in (
            "parent_span_id", "attempt", "retry_of_span_id", "model", "provider",
            "input_tokens", "output_tokens", "total_tokens", "cost",
        ):
            self.assertIsNone(read[column], column)
        self.assertEqual((read["input_payload"], read["output_payload"], read["error_payload"]), ("", "", ""))
        self.assertEqual((read["attributes"], read["events"], read["links"]), ({}, [], []))

    def test_fully_populated_span(self):
        started = 1_700_000_000_123_456_789
        span = make_span(
            span_id="2" * 16,
            parent_span_id="1" * 16,
            operation_type="model",
            span_name="llm.generate",
            display_label="Generate answer",
            execution_mode="live",
            graph_node_id="answer",
            graph_node_parent_id="retrieve",
            status_code="ERROR",
            status_description="provider timeout after retry",
            error_type="TimeoutError",
            started_at=started,
            ended_at=started + 864_197_532,
            attempt=2,
            retry_of_span_id="3" * 16,
            model="gpt-4o-mini",
            provider="openai",
            input_tokens=1200,
            output_tokens=345,
            total_tokens=1545,
            cost="0.00125",
            input_state="captured",
            input_payload='{"question": "Wie spät ist es? ✓"}',
            output_state="truncated",
            output_payload="The answer begins with a partial prefix",
            error_state="redacted",
            error_payload="[redacted]",
            attributes={"gen_ai.request.temperature": "0.2", "tenant": "ünïcode"},
            events=(
                {"name": "retry", "time": started + 1, "attributes": {"attempt": "1", "reason": "timeout"}},
                {"name": "first_token", "time": started + 500_000_001, "attributes": {"latency_ns": "500000001"}},
            ),
            links=({"trace_id": "f" * 32, "span_id": "3" * 16, "relation": "retry_of"},),
            received_at=1_700_000_001_999_999_999,
        )
        read = self.roundtrip(span, partition=2, offset=41)

        # Nanoseconds survive, including the last digit.
        self.assertEqual((read["started_at"], read["ended_at"]), (1_700_000_000_123_456_789, 1_700_000_000_987_654_321))
        self.assertEqual([e["time"] for e in read["events"]], [started + 1, started + 500_000_001])
        # received_at is stored in ms, truncated, as §8.2 decides.
        self.assertEqual(read["received_at"], 1_700_000_001_999)
        # Same number, different text: the column has scale 9.
        self.assertEqual(read["cost"], Decimal("0.00125"))
        self.assertEqual(str(read["cost"]), "0.001250000")
        self.assertEqual(
            (read["status_code"], read["input_state"], read["output_state"], read["error_state"]),
            ("ERROR", "captured", "truncated", "redacted"),
        )


if __name__ == "__main__":
    unittest.main()
