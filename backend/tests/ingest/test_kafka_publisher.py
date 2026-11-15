"""KafkaSpanPublisher against a real broker (the compose Kafka).

Each class gets a throwaway topic (3 partitions, like agentdbg.traces.v1),
deleted afterwards, so nothing lands in the real trace topic. The broker comes
from KAFKA_BOOTSTRAP_SERVERS (default localhost:9092). If it is unreachable
the class is skipped, unless KAFKA_REQUIRED=1, which makes it an error.
"""

import asyncio
import os
import time
import unittest
import uuid

from aiokafka import AIOKafkaConsumer, TopicPartition
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.record.default_records import DefaultRecordBatchBuilder

from agent_debugger_api.contracts import PublishError, SpanRecord, SpanTooLargeError
from agent_debugger_api.ingest.kafka_publisher import KafkaSpanPublisher
from tests.contracts.factories import TRACE_1, TRACE_2, make_span

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
PARTITIONS = 3
SMALL_LIMIT = 2048  # bytes per Kafka record; make_span() is well under it


def big_span():
    return make_span(span_id="b" * 16, input_state="captured", input_payload="x" * 4096)


async def _admin(action):
    admin = AIOKafkaAdminClient(bootstrap_servers=BOOTSTRAP, request_timeout_ms=5000)
    await admin.start()
    try:
        return await action(admin)
    finally:
        await admin.close()


async def read_all(topic: str, expected: int, timeout_s: float = 10.0):
    consumer = AIOKafkaConsumer(bootstrap_servers=BOOTSTRAP, enable_auto_commit=False)
    await consumer.start()
    try:
        partitions = [TopicPartition(topic, p) for p in range(PARTITIONS)]
        consumer.assign(partitions)
        await consumer.seek_to_beginning(*partitions)
        messages, deadline = [], time.monotonic() + timeout_s
        while len(messages) < expected and time.monotonic() < deadline:
            batch = await consumer.getmany(timeout_ms=500)
            messages.extend(m for records in batch.values() for m in records)
        return messages
    finally:
        await consumer.stop()


class KafkaTopicTestCase(unittest.IsolatedAsyncioTestCase):
    topic = ""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.topic = f"scratch.{cls.__name__.lower()}.{uuid.uuid4().hex[:8]}"
        try:
            asyncio.run(_admin(lambda a: a.create_topics(
                [NewTopic(cls.topic, num_partitions=PARTITIONS, replication_factor=1)])))
        except Exception as exc:  # unreachable broker or auth failure
            if os.environ.get("KAFKA_REQUIRED") == "1":
                raise RuntimeError(f"Kafka not reachable at {BOOTSTRAP}") from exc
            raise unittest.SkipTest(
                f"Kafka not reachable at {BOOTSTRAP} ({type(exc).__name__}). "
                "Start it with `docker compose up -d kafka kafka-init` to run these tests."
            ) from None
        cls.addClassCleanup(lambda: asyncio.run(_admin(lambda a: a.delete_topics([cls.topic]))))


class KafkaPublisherRoundTripTests(KafkaTopicTestCase):
    async def test_publish_then_read_back_one_message_per_span_keyed_by_trace(self):
        spans = [
            make_span(trace_id=TRACE_1),
            make_span(trace_id=TRACE_1, span_id="b" * 16, parent_span_id="a" * 16, attributes={"k": "v"}),
            make_span(trace_id=TRACE_2, cost="0.00125", events=({"name": "retry", "time": 1, "attributes": {}},)),
        ]
        publisher = KafkaSpanPublisher(BOOTSTRAP, self.topic, timeout_s=10)
        try:
            await publisher.publish(spans)
        finally:
            await publisher.close()

        messages = await read_all(self.topic, expected=3)
        self.assertEqual(len(messages), 3)
        by_span = {(m.key, SpanRecord.model_validate_json(m.value).span_id): m for m in messages}
        for span in spans:
            message = by_span[(span.trace_id.encode(), span.span_id)]
            # The value is the SpanRecord exactly (int ns, cost string, project_id, received_at).
            self.assertEqual(SpanRecord.model_validate_json(message.value), span)
        # Same key -> same partition: all spans of a trace stay together.
        trace_1_partitions = {m.partition for m in messages if m.key == TRACE_1.encode()}
        self.assertEqual(len(trace_1_partitions), 1)

    async def test_unknown_topic_raises_publish_error(self):
        # Auto topic creation is off on the compose broker, so this send is never acked.
        publisher = KafkaSpanPublisher(BOOTSTRAP, f"{self.topic}.missing", timeout_s=3)
        try:
            with self.assertRaises(PublishError):
                await publisher.publish([make_span()])
        finally:
            await publisher.close()


    async def test_oversized_span_publishes_nothing(self):
        publisher = KafkaSpanPublisher(BOOTSTRAP, self.topic, timeout_s=10, max_request_size=SMALL_LIMIT)
        try:
            with self.assertRaises(SpanTooLargeError) as raised:
                await publisher.publish([make_span(), big_span()])
        finally:
            await publisher.close()
        self.assertEqual(raised.exception.index, 1)
        # The small span went before the big one in the batch, and it is not in the topic either.
        self.assertEqual(await read_all(self.topic, expected=1, timeout_s=3), [])


class KafkaPublisherWithoutBrokerTests(unittest.IsolatedAsyncioTestCase):
    async def test_unreachable_broker_raises_publish_error(self):
        publisher = KafkaSpanPublisher("127.0.0.1:1", "agentdbg.traces.v1", timeout_s=5)
        try:
            with self.assertRaises(PublishError):
                await publisher.publish([make_span()])
        finally:
            await publisher.close()

    async def test_empty_publish_does_not_connect(self):
        publisher = KafkaSpanPublisher("127.0.0.1:1", "agentdbg.traces.v1", timeout_s=1)
        await publisher.publish([])
        self.assertIsNone(publisher._producer)


    async def test_oversized_span_raises_before_connecting(self):
        publisher = KafkaSpanPublisher("127.0.0.1:1", "agentdbg.traces.v1", max_request_size=SMALL_LIMIT)
        with self.assertRaises(SpanTooLargeError) as raised:
            await publisher.publish([make_span(), big_span()])
        error = raised.exception
        self.assertEqual((error.index, error.limit), (1, SMALL_LIMIT))
        self.assertGreater(error.size, SMALL_LIMIT)
        self.assertNotIsInstance(error, PublishError)  # 413, not a retryable 503
        self.assertIsNone(publisher._producer)

    async def test_limit_matches_what_the_producer_enforces(self):
        # A span exactly at the limit passes the pre-check; one byte more fails.
        span = make_span()
        size = DefaultRecordBatchBuilder.estimate_size_in_bytes(span.kafka_key, span.model_dump_json().encode(), [])
        producers = []
        at_limit = KafkaSpanPublisher("unused", "t", max_request_size=size,
                                      producer_factory=lambda: producers.append(FakeProducer()) or producers[-1])
        await at_limit.publish([span])
        self.assertEqual(len(producers[0].sent), 1)
        with self.assertRaises(SpanTooLargeError):
            await KafkaSpanPublisher("unused", "t", max_request_size=size - 1).publish([span])


class FakeProducer:
    """Stands in for AIOKafkaProducer. fail="send" raises from send(); fail="ack"
    returns a failed ack future; hang=True returns an ack that never resolves."""

    def __init__(self, fail=None, hang=False):
        self.fail, self.hang = fail, hang
        self.started = self.stopped = False
        self.sent = []

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def send(self, topic, value=None, key=None):
        if self.fail == "send":
            raise ConnectionError("broker connection lost")
        ack = asyncio.get_running_loop().create_future()
        if self.fail == "ack":
            ack.set_exception(ConnectionError("produce request failed"))
        elif not self.hang:
            self.sent.append((key, value))
            ack.set_result(None)
        return ack


class ProducerLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def publisher(self, *producers, timeout_s=5):
        queue = list(producers)
        self.created = []

        def factory():
            producer = queue.pop(0)
            self.created.append(producer)
            return producer

        return KafkaSpanPublisher("unused", "t", timeout_s=timeout_s, producer_factory=factory)

    async def test_failed_send_stops_and_replaces_the_producer(self):
        for mode in ("send", "ack"):
            with self.subTest(mode):
                broken, fresh = FakeProducer(fail=mode), FakeProducer()
                publisher = self.publisher(broken, fresh)
                with self.assertRaises(PublishError):
                    await publisher.publish([make_span()])
                self.assertTrue(broken.stopped)
                self.assertIsNone(publisher._producer)

                await publisher.publish([make_span()])
                self.assertEqual(self.created, [broken, fresh])
                self.assertEqual(len(fresh.sent), 1)
                self.assertIs(publisher._producer, fresh)

    async def test_healthy_producer_is_reused(self):
        producer = FakeProducer()
        publisher = self.publisher(producer)
        await publisher.publish([make_span()])
        await publisher.publish([make_span()])
        self.assertEqual(self.created, [producer])
        self.assertEqual(len(producer.sent), 2)

    async def test_timeout_keeps_the_producer(self):
        slow = FakeProducer(hang=True)
        publisher = self.publisher(slow, timeout_s=0.1)
        with self.assertRaises(PublishError):
            await publisher.publish([make_span()])
        self.assertFalse(slow.stopped)
        self.assertIs(publisher._producer, slow)


if __name__ == "__main__":
    unittest.main()
