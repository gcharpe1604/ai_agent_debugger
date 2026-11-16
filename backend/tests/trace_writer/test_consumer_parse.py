import unittest
from collections import namedtuple

from agent_debugger_api.trace_writer.consumer import parse_batch
from tests.contracts.factories import make_span

Msg = namedtuple("Msg", "value partition offset")


class ParseBatchTest(unittest.TestCase):
    def test_good_and_bad_messages_are_split(self):
        good = make_span().model_dump_json().encode()
        batch = parse_batch([
            Msg(good, 0, 10),
            Msg(b"not json", 0, 11),
            Msg(None, 1, 5),
        ])
        self.assertEqual(len(batch.records), 1)
        self.assertEqual(batch.positions, [(0, 10)])
        self.assertEqual(len(batch.bad), 2)