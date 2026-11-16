from dataclasses import dataclass, field

from pydantic import ValidationError
import asyncio
import logging

from agent_debugger_api.contracts.span_record import SpanRecord

@dataclass
class ParsedBatch:
    records: list[SpanRecord] = field(default_factory=list)
    positions: list[tuple[int, int]] = field(default_factory=list)
    bad: list[tuple[object, str]] = field(default_factory=list)


def parse_batch(messages) -> ParsedBatch:
    out = ParsedBatch()
    for msg in messages:
        if msg.value is None:                         # empty message: can never be a span
            out.bad.append((msg, "empty message"))
            continue
        try:
            record = SpanRecord.model_validate_json(msg.value)
        except ValidationError as exc:
            out.bad.append((msg, str(exc)))
            continue
        out.records.append(record)
        out.positions.append((msg.partition, msg.offset))
    return out



log = logging.getLogger(__name__)


async def send_to_dlq(producer, dlq_topic, bad) -> None:
    """Send each bad message to the DLQ and wait for the ack."""
    for msg, error in bad:
        await producer.send_and_wait(
            dlq_topic,
            value=msg.value or b"",
            key=msg.key,
            headers=[
                ("error", error[:1000].encode()),
                ("source", f"{msg.topic}:{msg.partition}:{msg.offset}".encode()),
            ],
        )


async def insert_with_retry(store, batch, stop) -> bool:
    """Retry the SAME batch until ClickHouse accepts it. False = shutting down."""
    delay = 0.5
    while True:
        try:
            await asyncio.to_thread(store.insert_spans, batch.records, batch.positions)
            return True
        except Exception:
            log.exception("insert failed, retrying in %.1fs", delay)
            if stop.is_set():
                return False
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)


async def run(consumer, producer, store, dlq_topic, stop, max_records=1000, timeout_ms=1000):
    while not stop.is_set():
        result = await consumer.getmany(timeout_ms=timeout_ms, max_records=max_records)
        messages = [m for msgs in result.values() for m in msgs]
        if not messages:
            continue
        batch = parse_batch(messages)
        if batch.bad:
            await send_to_dlq(producer, dlq_topic, batch.bad)                   # raises -> no commit
        if batch.records and not await insert_with_retry(store, batch, stop):
            return                                                              # stopping: no commit
        await consumer.commit()                                                 # only after everything is safe