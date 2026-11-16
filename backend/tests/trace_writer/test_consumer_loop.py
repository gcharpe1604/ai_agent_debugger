import asyncio
import unittest
from collections import namedtuple

from agent_debugger_api.contracts.fakes import InMemoryTraceStore
from agent_debugger_api.trace_writer.consumer import run
from agent_debugger_api.trace_writer.content_hash import content_hash
from tests.contracts.factories import make_span

Msg = namedtuple("Msg", "value partition offset topic key")


class FakeConsumer:
    def __init__(self, batches, stop):
        self.batches = list(batches)
        self.stop = stop
        self.commits = 0

    async def getmany(self, timeout_ms, max_records):
        if not self.batches:
            self.stop.set()
            return {}
        return {"tp": self.batches.pop(0)}

    async def commit(self):
        self.commits += 1


class FakeProducer:
    def __init__(self):
        self.sent = []

    async def send_and_wait(self, topic, value, key, headers):
        self.sent.append((topic, value))


class FlakyStore(InMemoryTraceStore):
    def __init__(self, failures):
        super().__init__(content_hash=content_hash)
        self.failures = failures

    def insert_spans(self, spans, positions=None):
        if self.failures:
            self.failures -= 1
            raise ConnectionError("clickhouse is down")
        super().insert_spans(spans, positions)


def msg(span, offset):
    return Msg(span.model_dump_json().encode(), 0, offset, "t", None)


class ConsumerLoopTest(unittest.IsolatedAsyncioTestCase):
    async def test_good_batch_is_inserted_then_committed(self):
        stop, span = asyncio.Event(), make_span()
        consumer, producer, store = FakeConsumer([[msg(span, 1)]], stop), FakeProducer(), InMemoryTraceStore(content_hash=content_hash)
        await run(consumer, producer, store, "dlq", stop)
        self.assertIsNotNone(store.get_trace(span.project_id, span.trace_id))
        self.assertEqual(consumer.commits, 1)
        self.assertEqual(producer.sent, [])

    async def test_bad_message_goes_to_dlq_and_good_one_is_stored(self):
        stop, span = asyncio.Event(), make_span()
        batch = [msg(span, 1), Msg(b"not json", 0, 2, "t", None)]
        consumer, producer, store = FakeConsumer([batch], stop), FakeProducer(), InMemoryTraceStore(content_hash=content_hash)
        await run(consumer, producer, store, "dlq", stop)
        self.assertEqual([t for t, _ in producer.sent], ["dlq"])
        self.assertIsNotNone(store.get_trace(span.project_id, span.trace_id))
        self.assertEqual(consumer.commits, 1)

    async def test_clickhouse_down_retries_then_commits_once(self):
        stop, span = asyncio.Event(), make_span()
        consumer, producer, store = FakeConsumer([[msg(span, 1)]], stop), FakeProducer(), FlakyStore(2)
        await run(consumer, producer, store, "dlq", stop)
        self.assertEqual(store.failures, 0)                       # failed twice, then succeeded
        self.assertEqual(consumer.commits, 1)                     # committed only after success