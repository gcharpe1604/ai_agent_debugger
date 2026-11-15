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
from collections.abc import Sequence

from aiokafka import AIOKafkaProducer

from agent_debugger_api.contracts import PublishError, SpanRecord


class KafkaSpanPublisher:
    """One message per span: key = trace_id, value = SpanRecord JSON.

    `publish` returns only when every span is acked by the broker
    (acks="all"); any failure or timeout raises PublishError. Spans acked
    before a failure stay in Kafka (§8.3); a client retry redelivers them and
    option A dedup makes that harmless.

    The producer starts on the first publish, not at app start, so the API
    (and the local profile) runs without Kafka until a durable batch arrives.
    """

    def __init__(self, bootstrap_servers: str, topic: str, timeout_s: float = 10.0) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.timeout_s = timeout_s
        self._producer: AIOKafkaProducer | None = None
        self._start_lock: asyncio.Lock | None = None

    async def publish(self, spans: Sequence[SpanRecord]) -> None:
        if not spans:
            return
        try:
            await asyncio.wait_for(self._send_all(spans), timeout=self.timeout_s)
        except PublishError:
            raise
        except asyncio.TimeoutError as exc:
            raise PublishError(f"Kafka did not ack {len(spans)} span(s) within {self.timeout_s} s") from exc
        except Exception as exc:  # any client or broker error: never report success
            raise PublishError(f"Kafka publish failed: {type(exc).__name__}") from exc

    async def _send_all(self, spans: Sequence[SpanRecord]) -> None:
        producer = await self._started_producer()
        # Enqueue every record first so they go out in as few requests as possible,
        # then wait for all acks. gather raises on the first failed ack.
        acks = [
            await producer.send(self.topic, value=span.model_dump_json().encode("utf-8"), key=span.kafka_key)
            for span in spans
        ]
        await asyncio.gather(*acks)

    async def _started_producer(self) -> AIOKafkaProducer:
        if self._producer is not None:
            return self._producer
        if self._start_lock is None:
            self._start_lock = asyncio.Lock()
        async with self._start_lock:
            if self._producer is None:
                producer = AIOKafkaProducer(
                    bootstrap_servers=self.bootstrap_servers,
                    acks="all",
                    # Broker-side dedup of the client's own internal retries.
                    enable_idempotence=True,
                )
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
