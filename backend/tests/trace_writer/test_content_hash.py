import unittest
from uuid import uuid4

from agent_debugger_api.contracts.span_record import SpanRecord
from agent_debugger_api.trace_writer.content_hash import EXCLUDED_FIELDS, content_hash
from tests.contracts.factories import make_span


class ContentHashTests(unittest.TestCase):
    def test_attribute_order_does_not_change_hash(self):
        a = make_span(attributes={"x": "1", "y": "2"})
        b = make_span(attributes={"y": "2", "x": "1"})
        self.assertEqual(content_hash(a), content_hash(b))

    def test_delivery_fields_do_not_change_hash(self):
        a = make_span()
        b = a.model_copy(update={"received_at": a.received_at + 1, "project_id": uuid4()})
        self.assertEqual(content_hash(a), content_hash(b))

    def test_content_change_changes_hash(self):
        a = make_span()
        b = a.model_copy(update={"span_name": "something else"})
        self.assertNotEqual(content_hash(a), content_hash(b))

    def test_hashed_fields_are_classified_explicitly(self):
        # Adding a SpanRecord field fails this test until it is deliberately
        # classified: span content (hashed) or delivery metadata (EXCLUDED_FIELDS).
        hashed = {
            "attempt", "attributes", "cost", "display_label", "ended_at",
            "error_payload", "error_state", "error_type", "events", "execution_mode",
            "graph_node_id", "graph_node_parent_id", "input_payload", "input_state",
            "input_tokens", "links", "model", "operation_type", "output_payload",
            "output_state", "output_tokens", "parent_span_id", "provider",
            "retry_of_span_id", "service_name", "span_id", "span_name", "started_at",
            "status_code", "status_description", "total_tokens", "trace_id",
        }
        self.assertEqual(EXCLUDED_FIELDS, {"project_id", "received_at", "protocol_version"})
        self.assertEqual(set(SpanRecord.model_fields) - EXCLUDED_FIELDS, hashed)
        self.assertEqual(set(make_span().model_dump(mode="json", exclude=EXCLUDED_FIELDS)), hashed)
