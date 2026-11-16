"""Trace-writer consumer against real Kafka and ClickHouse (clickhouse-span-record.md §6 tests 2, 14-16).

Each test gets a throwaway trace topic (3 partitions), DLQ topic and consumer
group, all deleted or abandoned afterwards, plus the class's scratch ClickHouse
database; nothing touches `agentdbg.traces.v1` or `telemetry`. The writer is
consumer.run() with real AIOKafkaConsumer/AIOKafkaProducer and
ClickHouseTraceStore, wired like trace_writer.__main__.

Kafka comes from KAFKA_BOOTSTRAP_SERVERS (default localhost:9092). If it is
unreachable the test is skipped, unless KAFKA_REQUIRED=1 (CI), which makes it
an error. ClickHouse follows tests/clickhouse/harness.py.
"""

import asyncio
import os
import time
import unittest
import uuid

from agent_debugger_api.trace_writer.clickhouse_store import ClickHouseTraceStore
from agent_debugger_api.trace_writer.consumer import run
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, TopicPartition
from aiokafka.admin import AIOKafkaAdminClient, NewTopic

from tests.clickhouse.harness import ClickHouseTestCase, clickhouse_client
from tests.contracts.factories import PROJECT_A, make_span

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
PARTITIONS = 3


def trace(n: int) -> str:
    return f"{n:032x}"


class Crash(BaseException):
    """Stands in for the process dying. Not an Exception, so insert_with_retry cannot catch it."""


class CrashPoint:
    """The process dies between a batch's two side effects (insert and commit).

    Whichever of the two comes second raises Crash instead of running, once.
    With the real order (insert, then commit) that is "after the insert, before
    the commit"; it does not depend on which order consumer.run() uses.
    """

    def __init__(self) -> None:
        self.armed = True
        self.done: list[str] = []

    def step(self, name: str) -> None:
        if self.armed and self.done:
            self.armed = False
            raise Crash(f"died before {name}, after {self.done[0]}")
        self.done.append(name)


class RecordingConsumer:
    """Passes through to an AIOKafkaConsumer; records batch sizes and can crash before commit."""

    def __init__(self, inner: AIOKafkaConsumer, point: CrashPoint | None = None) -> None:
        self.inner, self.point = inner, point
        self.batches: list[int] = []

    async def getmany(self, timeout_ms, max_records):
        result = await self.inner.getmany(timeout_ms=timeout_ms, max_records=max_records)
        size = sum(len(messages) for messages in result.values())
        if size:
            self.batches.append(size)
        return result

    async def commit(self):
        if self.point:
            self.point.step("commit")
        await self.inner.commit()


class RecordingStore:
    """Passes through to ClickHouseTraceStore; records INSERT sizes and can crash before insert."""

    def __init__(self, inner: ClickHouseTraceStore, point: CrashPoint | None = None) -> None:
        self.inner, self.point = inner, point
        self.inserts: list[int] = []

    def insert_spans(self, spans, positions=None):
        if self.point:
            self.point.step("insert")
        self.inner.insert_spans(spans, positions)
        self.inserts.append(len(spans))


class WriterKafkaTests(ClickHouseTestCase, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        suffix = uuid.uuid4().hex[:8]
        self.topic = f"scratch.writer.{suffix}"
        self.dlq = f"{self.topic}.dlq"
        self.group = f"scratch-writer-{suffix}"
        try:
            await self._admin(lambda a: a.create_topics([
                NewTopic(self.topic, num_partitions=PARTITIONS, replication_factor=1),
                NewTopic(self.dlq, num_partitions=1, replication_factor=1),
            ]))
        except Exception as exc:  # unreachable broker
            if os.environ.get("KAFKA_REQUIRED") == "1":
                raise RuntimeError(f"Kafka not reachable at {BOOTSTRAP}") from exc
            raise unittest.SkipTest(f"Kafka not reachable at {BOOTSTRAP} ({type(exc).__name__})") from None
        self.addAsyncCleanup(self._admin, lambda a: a.delete_topics([self.topic, self.dlq]))
        # The writer gets its own ClickHouse session: the test polls on self.client
        # while the writer inserts, and one session cannot run two queries at once.
        self.writer_client = clickhouse_client()
        self.addCleanup(self.writer_client.close)
        self.store = ClickHouseTraceStore(self.writer_client, table=self.table)

    # Kafka helpers
    @staticmethod
    async def _admin(action):
        admin = AIOKafkaAdminClient(bootstrap_servers=BOOTSTRAP, request_timeout_ms=5000)
        await admin.start()
        try:
            return await action(admin)
        finally:
            await admin.close()

    async def publish(self, messages):
        """messages: (key, value) pairs, sent in order and acked."""
        producer = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP, acks="all")
        await producer.start()
        try:
            for key, value in messages:
                await producer.send_and_wait(self.topic, value=value, key=key)
        finally:
            await producer.stop()

    async def committed(self) -> int:
        """Messages the group has committed on the trace topic (offsets start at 0)."""
        offsets = await self._admin(lambda a: a.list_consumer_group_offsets(self.group))
        return sum(meta.offset for tp, meta in offsets.items() if tp.topic == self.topic and meta.offset > 0)

    async def read_dlq(self, expected: int, timeout_s: float = 10.0):
        consumer = AIOKafkaConsumer(bootstrap_servers=BOOTSTRAP, enable_auto_commit=False)
        await consumer.start()
        try:
            tp = TopicPartition(self.dlq, 0)
            consumer.assign([tp])
            await consumer.seek_to_beginning(tp)
            messages, deadline = [], time.monotonic() + timeout_s
            while len(messages) < expected and time.monotonic() < deadline:
                batch = await consumer.getmany(timeout_ms=300)
                messages.extend(m for records in batch.values() for m in records)
            return messages
        finally:
            await consumer.stop()

    async def run_writer(self, until, *, consumer_point=None, store=None, dlq=None, producer_kwargs=None, timeout_s=20.0):
        """Run consumer.run() until `until()` is true or the writer stops on its own.

        Returns (exception raised by run() or None, RecordingConsumer).
        """
        consumer = AIOKafkaConsumer(
            self.topic, bootstrap_servers=BOOTSTRAP, group_id=self.group,
            enable_auto_commit=False, auto_offset_reset="earliest",
        )
        producer = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP, acks="all", **(producer_kwargs or {}))
        await consumer.start()
        await producer.start()
        recording = RecordingConsumer(consumer, consumer_point)
        stop = asyncio.Event()
        task = asyncio.create_task(run(recording, producer, store or self.store, dlq or self.dlq, stop, timeout_ms=200))
        try:
            deadline = time.monotonic() + timeout_s
            while not task.done() and time.monotonic() < deadline and not await until():
                await asyncio.sleep(0.2)
            stop.set()  # run() finishes the current batch (insert + commit), then returns
            done, _ = await asyncio.wait({task}, timeout=15)
            if not done:
                task.cancel()
                self.fail("writer did not stop within 15 s")
            return task.exception(), recording
        finally:
            await consumer.stop()  # no commit on stop: auto-commit is off
            await producer.stop()

    # ClickHouse helpers
    def logical_span_ids(self, trace_id: str) -> list[str]:
        rows = ClickHouseTraceStore(self.client, table=self.table).get_rows(PROJECT_A, trace_id)
        return sorted(row["span_id"] for row in rows)

    def physical_rows(self, trace_id: str) -> int:
        return self.client.query(
            f"SELECT count() FROM {self.table} WHERE trace_id = %(t)s", parameters={"t": trace_id}
        ).result_rows[0][0]

    @staticmethod
    def span_message(span):
        return span.kafka_key, span.model_dump_json().encode("utf-8")

    def committed_at_least(self, n):
        async def check():
            return await self.committed() >= n
        return check

    # §6 test 2
    async def test_crash_after_insert_before_commit_loses_nothing_and_stays_one_logical_row(self):
        t = trace(201)
        spans = [make_span(trace_id=t, span_id=f"{i + 1:016x}", started_at=1_763_000_000_000_000_000 + i) for i in range(3)]
        await self.publish([self.span_message(s) for s in spans])

        point = CrashPoint()
        store = RecordingStore(self.store, point)

        async def never():
            return False

        error, _ = await self.run_writer(never, consumer_point=point, store=store)
        self.assertIsInstance(error, Crash, f"first writer should die mid-batch, got {error!r}")
        committed_at_crash = await self.committed()
        first_insert = sum(store.inserts)

        # Restart: same group, plain writer. It must re-read whatever was not committed.
        error, _ = await self.run_writer(self.committed_at_least(3))
        self.assertIsNone(error)

        # No message lost: every span is stored, each once logically.
        self.assertEqual(self.logical_span_ids(t), sorted(s.span_id for s in spans))
        self.assertEqual(await self.committed(), 3)
        self.assertEqual(committed_at_crash, 0, "nothing may be committed before the crash")
        # The crash happened after the insert: the crashed batch was inserted twice
        # physically (original + redelivery) and LIMIT 1 BY hides the duplicate.
        self.assertEqual(point.done, ["insert"])
        self.assertGreater(first_insert, 0)
        self.assertEqual(self.physical_rows(t), 3 + first_insert)

    # §6 test 14
    async def test_mixed_batch_inserts_valid_spans_and_dead_letters_invalid_ones(self):
        t = trace(214)
        good = [make_span(trace_id=t, span_id=f"{i + 1:016x}") for i in range(2)]
        key = good[0].kafka_key  # one key: one partition, in this order
        await self.publish([self.span_message(good[0]), (key, b"not json"), self.span_message(good[1])])
        store = RecordingStore(self.store)

        error, consumer = await self.run_writer(self.committed_at_least(3), store=store)

        self.assertIsNone(error)
        self.assertEqual(self.logical_span_ids(t), sorted(s.span_id for s in good))
        # One INSERT per batch that had valid spans, never one per span.
        self.assertEqual(sum(store.inserts), 2)
        self.assertLessEqual(len(store.inserts), len(consumer.batches))
        [dead] = await self.read_dlq(expected=1)
        headers = dict(dead.headers)
        self.assertEqual(dead.value, b"not json")
        self.assertEqual(dead.key, key)
        self.assertTrue(headers["error"])
        topic, partition, offset = headers["source"].decode().rsplit(":", 2)
        self.assertEqual((topic, offset), (self.topic, "1"))
        self.assertIn(int(partition), range(PARTITIONS))
        self.assertEqual(await self.committed(), 3)

    # §6 test 15
    async def test_all_invalid_batch_commits_without_insert(self):
        key = trace(215).encode()
        bad = [
            (key, b"not json"),
            (key, b'{"trace_id": "short"}'),  # JSON, but not a SpanRecord
            (key, None),  # empty message (tombstone)
        ]
        await self.publish(bad)
        store = RecordingStore(self.store)

        error, _ = await self.run_writer(self.committed_at_least(3), store=store)

        self.assertIsNone(error)
        self.assertEqual(store.inserts, [], "no INSERT for an all-invalid batch")
        dead = await self.read_dlq(expected=3)
        self.assertEqual([m.value for m in dead], [b"not json", b'{"trace_id": "short"}', b""])
        self.assertEqual(dict(dead[2].headers)["error"], b"empty message")
        self.assertEqual(await self.committed(), 3)

    # §6 test 16
    async def test_dlq_publish_failure_does_not_commit_and_restart_recovers(self):
        t = trace(216)
        good = make_span(trace_id=t)
        await self.publish([self.span_message(good), (good.kafka_key, b"not json")])

        # Auto topic creation is off, so a missing DLQ topic makes the DLQ send fail.
        missing_dlq = f"{self.dlq}.missing"
        error, _ = await self.run_writer(
            self.committed_at_least(2), dlq=missing_dlq, producer_kwargs={"request_timeout_ms": 3000}
        )
        self.assertIsNotNone(error, "the DLQ failure must stop the writer")
        self.assertNotIsInstance(error, Crash)
        self.assertEqual(await self.committed(), 0, "no commit after a failed DLQ publish")
        self.assertEqual(self.logical_span_ids(t), [], "DLQ runs before the insert, so nothing was stored")

        # Restart with the DLQ reachable: the same messages are read again and land as in test 15.
        error, _ = await self.run_writer(self.committed_at_least(2))
        self.assertIsNone(error)
        self.assertEqual(self.logical_span_ids(t), [good.span_id])
        [dead] = await self.read_dlq(expected=1)
        self.assertEqual(dead.value, b"not json")
        self.assertEqual(await self.committed(), 2)


if __name__ == "__main__":
    unittest.main()
