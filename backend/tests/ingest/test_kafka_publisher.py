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

from agent_debugger_api.contracts import PublishError, SpanRecord
from agent_debugger_api.ingest.kafka_publisher import KafkaSpanPublisher
from tests.contracts.factories import TRACE_1, TRACE_2, make_span

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
PARTITIONS = 3


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


if __name__ == "__main__":
    unittest.main()
