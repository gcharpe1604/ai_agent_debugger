"""`SpanPublisher` on Kafka (clickhouse-span-record.md §8.2, §8.3).

Client: aiokafka. It is asyncio-native, so `publish` awaits the broker acks
directly; `send()` returns a future that resolves when the broker acks that
record. confluent-kafka (librdkafka) is faster but callback/poll based and
needs a thread bridge into the event loop; throughput is not the constraint
here. Checked against the compose broker (apache/kafka 4.3.2, KRaft) with
aiokafka 0.13.0.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable, Sequence

from aiokafka import AIOKafkaProducer
from aiokafka.record.default_records import DefaultRecordBatchBuilder

from agent_debugger_api.contracts import PublishError, SpanRecord, SpanTooLargeError

# aiokafka's default. The broker's own limit (message.max.bytes, default
# 1,048,588) is slightly larger, so the producer limit is the one that bites.
DEFAULT_MAX_REQUEST_SIZE = 1_048_576


class KafkaSpanPublisher:
    """One message per span: key = trace_id, value = SpanRecord JSON.

    `publish` returns only when every span is acked by the broker
    (acks="all"); any failure or timeout raises PublishError. Spans acked
    before a failure stay in Kafka (§8.3); a client retry redelivers them and
    option A dedup makes that harmless.

    Every span is encoded and size-checked before anything is sent: a span
    larger than `max_request_size` raises SpanTooLargeError and the batch
    is not published at all (no retry can succeed).

    The producer starts on the first publish, not at app start, so the API
    (and the local profile) runs without Kafka until a durable batch arrives.
    After a send fails (other than by timeout) the producer is stopped and
    dropped, and the next publish starts a new one.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        timeout_s: float = 10.0,
        max_request_size: int = DEFAULT_MAX_REQUEST_SIZE,
        producer_factory: Callable[[], AIOKafkaProducer] | None = None,
    ) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.timeout_s = timeout_s
        self.max_request_size = max_request_size
        self._producer_factory = producer_factory or self._new_producer
        self._producer: AIOKafkaProducer | None = None
        self._start_lock: asyncio.Lock | None = None

    async def publish(self, spans: Sequence[SpanRecord]) -> None:
        if not spans:
            return
        records = self._encode(spans)  # SpanTooLargeError before any send
        try:
            await asyncio.wait_for(self._send_all(records), timeout=self.timeout_s)
        except PublishError:
            raise
        except asyncio.TimeoutError as exc:
            raise PublishError(f"Kafka did not ack {len(spans)} span(s) within {self.timeout_s} s") from exc
        except Exception as exc:  # any client or broker error: never report success
            raise PublishError(f"Kafka publish failed: {type(exc).__name__}") from exc

    def _encode(self, spans: Sequence[SpanRecord]) -> list[tuple[bytes, bytes]]:
        records = []
        for index, span in enumerate(spans):
            key, value = span.kafka_key, span.model_dump_json().encode("utf-8")
            # The same estimate AIOKafkaProducer.send() checks against max_request_size.
            size = DefaultRecordBatchBuilder.estimate_size_in_bytes(key, value, [])
            if size > self.max_request_size:
                raise SpanTooLargeError(index, size, self.max_request_size)
            records.append((key, value))
        return records

    async def _send_all(self, records: list[tuple[bytes, bytes]]) -> None:
        producer = await self._started_producer()
        try:
            # Enqueue every record first so they go out in as few requests as possible,
            # then wait for all acks. gather raises on the first failed ack.
            acks = [await producer.send(self.topic, value=value, key=key) for key, value in records]
            await asyncio.gather(*acks)
        except Exception:
            # The producer may be in a bad state (broken connection, fatal
            # idempotence error): replace it. A timeout cancels this coroutine
            # (CancelledError is not an Exception), so a slow broker keeps it.
            await self._discard(producer)
            raise

    async def _discard(self, producer: AIOKafkaProducer) -> None:
        # Only the current producer: a concurrent publish may already have replaced it.
        if self._producer is producer:
            self._producer = None
        with contextlib.suppress(Exception):
            await producer.stop()

    def _new_producer(self) -> AIOKafkaProducer:
        return AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            acks="all",
            # Broker-side dedup of the client's own internal retries.
            enable_idempotence=True,
            max_request_size=self.max_request_size,
        )

    async def _started_producer(self) -> AIOKafkaProducer:
        if self._producer is not None:
            return self._producer
        if self._start_lock is None:
            self._start_lock = asyncio.Lock()
        async with self._start_lock:
            if self._producer is None:
                producer = self._producer_factory()
                try:
                    await producer.start()
                except BaseException:
                    await producer.stop()
                    raise
                self._producer = producer
        return self._producer

    async def close(self) -> None:
        if self._producer is not None:
            producer, self._producer = self._producer, None
            await producer.stop()
