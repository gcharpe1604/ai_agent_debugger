import unittest
from uuid import uuid4

from agent_debugger_api.trace_writer.content_hash import content_hash
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
