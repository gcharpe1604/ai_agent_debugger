import json
import unittest

from pydantic import ValidationError

from agent_debugger_api.contracts import PayloadState, SpanRecord, StatusCode
from tests.contracts.factories import T0, make_span, span_fields


class SpanRecordTests(unittest.TestCase):
    def test_minimal_span_is_valid_and_nulls_stay_null(self):
        span = make_span()
        self.assertIs(span.status_code, StatusCode.OK)
        self.assertIs(span.error_state, PayloadState.UNAVAILABLE)
        for field in ("model", "provider", "input_tokens", "output_tokens", "total_tokens", "cost"):
            self.assertIsNone(getattr(span, field), field)
        self.assertEqual(span.duration_ns, 1_000)
        self.assertEqual(span.kafka_key, b"1" * 32)

    def test_json_round_trip_keeps_int_ns_and_cost_string(self):
        span = make_span(cost="0.001250000", input_tokens=10, events=[{"name": "e", "time": T0 + 1}])
        raw = span.model_dump_json()
        data = json.loads(raw)
        self.assertIsInstance(data["started_at"], int)
        self.assertIsInstance(data["events"][0]["time"], int)
        self.assertEqual(data["cost"], "0.001250000")
        self.assertEqual(SpanRecord.model_validate_json(raw), span)

    def test_writer_owned_and_unknown_fields_are_rejected(self):
        for field in ("content_hash", "persisted_at", "kafka_partition", "kafka_offset", "duration_ns", "x"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                SpanRecord.model_validate(span_fields(**{field: 1}))

    def test_timestamps_must_be_integer_ns(self):
        for bad in ("1763000000000000000", 1.5, True, -1, 2**63, "2026-11-13T00:00:00Z"):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                make_span(started_at=bad)
        with self.assertRaises(ValidationError):
            SpanRecord.model_validate_json(json.dumps(span_fields(project_id="00000000-0000-4000-8000-00000000000a", ended_at=1.0e18)))

    def test_ended_before_started_is_rejected(self):
        with self.assertRaises(ValidationError):
            make_span(started_at=T0, ended_at=T0 - 1)

    def test_cost_must_be_a_decimal_string(self):
        for good in ("0", "12.5", "123456789.123456789"):
            self.assertEqual(make_span(cost=good).cost, good)
        for bad in (0.00125, 1, "-1", "1e-3", "0.1234567891", "1234567890", ""):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                make_span(cost=bad)

    def test_ids_must_be_lowercase_hex_of_the_right_length(self):
        for field, bad in (("trace_id", "A" * 32), ("trace_id", "1" * 31), ("span_id", "g" * 16), ("parent_span_id", "")):
            with self.subTest(field=field, bad=bad), self.assertRaises(ValidationError):
                make_span(**{field: bad})

    def test_payload_states_are_required_and_enumerated(self):
        fields = span_fields()
        del fields["input_state"]
        with self.assertRaises(ValidationError):
            SpanRecord.model_validate(fields)
        with self.assertRaises(ValidationError):
            make_span(output_state="missing")

    def test_disabled_or_unavailable_payload_must_be_empty(self):
        for state in ("disabled", "unavailable"):
            with self.subTest(state=state), self.assertRaises(ValidationError):
                make_span(input_state=state, input_payload="null")
        truncated = make_span(output_state="truncated", output_payload='{"a": "pre')
        self.assertEqual(truncated.output_payload, '{"a": "pre')

    def test_enums_and_literals_reject_unknown_values(self):
        for field, bad in (
            ("status_code", "FAILED"),
            ("operation_type", "llm"),
            ("protocol_version", "local-1"),
        ):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                make_span(**{field: bad})

    def test_execution_mode_is_any_string(self):
        self.assertEqual(make_span(execution_mode="replay").execution_mode, "replay")
        with self.assertRaises(ValidationError):
            make_span(execution_mode=1)

    def test_attributes_are_string_to_string(self):
        with self.assertRaises(ValidationError):
            make_span(attributes={"tokens": 3})

    def test_records_are_immutable(self):
        with self.assertRaises(ValidationError):
            make_span().span_name = "changed"


if __name__ == "__main__":
    unittest.main()
