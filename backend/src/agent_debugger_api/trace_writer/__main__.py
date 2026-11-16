import asyncio
import logging
import signal

import clickhouse_connect
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from .clickhouse_store import ClickHouseTraceStore
from .consumer import run
from .settings import WriterSettings


async def main() -> None:
    s = WriterSettings()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)   # finish the current batch, then exit
        except NotImplementedError:
            pass                                     # Windows: Ctrl+C stops it via KeyboardInterrupt

    client = clickhouse_connect.get_client(
        host=s.clickhouse_host, port=s.clickhouse_port,
        username=s.clickhouse_user, password=s.clickhouse_password,
    )
    store = ClickHouseTraceStore(client, table=f"{s.clickhouse_database}.telemetry_spans")

    consumer = AIOKafkaConsumer(
        s.kafka_trace_topic,
        bootstrap_servers=s.kafka_bootstrap_servers,
        group_id=s.kafka_trace_writer_group,
        enable_auto_commit=False,          # WE decide when to commit (after the insert)
        auto_offset_reset="earliest",      # a brand-new group starts from the first message
    )
    producer = AIOKafkaProducer(bootstrap_servers=s.kafka_bootstrap_servers, acks="all")
    await consumer.start()
    await producer.start()
    try:
        await run(consumer, producer, store, s.kafka_trace_dlq_topic, stop,
                  s.batch_max_records, s.batch_timeout_ms)
    finally:
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())