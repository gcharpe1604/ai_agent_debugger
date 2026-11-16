"""Helper for scripts/demo_durable.ps1. Run with the backend environment:

    uv run --project backend --locked python -B scripts/demo_durable_check.py <command> [args]

Commands:
    wait-schema [timeout_s]          wait until telemetry.telemetry_spans exists (writer startup)
    wait-caught-up [timeout_s]       wait until the writer group has committed every message on the trace topic
    report <trace_id>                physical rows vs ClickHouseTraceStore.get_trace, get_conflicts, list_runs

Settings come from WriterSettings (same .env and defaults as the writer).
Exit code 1 when a wait times out.
"""

import asyncio
import sys
import time

import clickhouse_connect
from aiokafka import AIOKafkaConsumer, TopicPartition
from aiokafka.admin import AIOKafkaAdminClient

from agent_debugger_api.ingest.settings import resolve_project_id
from agent_debugger_api.trace_writer.clickhouse_store import ClickHouseTraceStore
from agent_debugger_api.trace_writer.schema import TABLE
from agent_debugger_api.trace_writer.settings import WriterSettings

S = WriterSettings()
FULL_TABLE = f"{S.clickhouse_database}.{TABLE}"


def clickhouse():
    return clickhouse_connect.get_client(
        host=S.clickhouse_host, port=S.clickhouse_port,
        username=S.clickhouse_user, password=S.clickhouse_password,
    )


def wait_schema(timeout_s: float) -> int:
    client, deadline = clickhouse(), time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        exists = client.command(f"EXISTS TABLE {FULL_TABLE}")
        if str(exists) == "1":
            print(f"{FULL_TABLE} exists")
            return 0
        time.sleep(0.5)
    print(f"timed out after {timeout_s:.0f} s: {FULL_TABLE} not created (is the writer running? see its log)")
    return 1


async def lag() -> tuple[int, dict[int, tuple[int, int]]]:
    """Total lag of the writer group on the trace topic, and (committed, end) per partition."""
    consumer = AIOKafkaConsumer(bootstrap_servers=S.kafka_bootstrap_servers)
    await consumer.start()
    admin = AIOKafkaAdminClient(bootstrap_servers=S.kafka_bootstrap_servers)
    await admin.start()
    try:
        [topic] = await admin.describe_topics([S.kafka_trace_topic])
        partitions = [TopicPartition(S.kafka_trace_topic, p["partition"]) for p in sorted(topic["partitions"], key=lambda p: p["partition"])]
        ends = await consumer.end_offsets(partitions)
        committed = await admin.list_consumer_group_offsets(S.kafka_trace_writer_group)
        per_partition, total = {}, 0
        for tp in partitions:
            meta = committed.get(tp)
            done = meta.offset if meta is not None and meta.offset >= 0 else 0
            per_partition[tp.partition] = (done, ends[tp])
            total += max(ends[tp] - done, 0)
        return total, per_partition
    finally:
        await admin.close()
        await consumer.stop()


def wait_caught_up(timeout_s: float) -> int:
    deadline = time.monotonic() + timeout_s
    while True:
        total, per_partition = asyncio.run(lag())
        if total == 0:
            shown = ", ".join(f"p{p}: {done}/{end}" for p, (done, end) in per_partition.items())
            print(f"group {S.kafka_trace_writer_group} caught up (committed/end: {shown})")
            return 0
        if time.monotonic() > deadline:
            print(f"timed out after {timeout_s:.0f} s: lag {total} ({per_partition})")
            return 1
        time.sleep(0.5)


def report(trace_id: str) -> int:
    client = clickhouse()
    store = ClickHouseTraceStore(client, table=FULL_TABLE)
    project = resolve_project_id()
    params = {"p": str(project), "t": trace_id}
    where = "project_id = %(p)s AND trace_id = %(t)s"

    physical = client.query(f"SELECT count() FROM {FULL_TABLE} WHERE {where}", parameters=params).result_rows[0][0]
    per_span = client.query(
        f"SELECT span_id, span_name, count() AS copies FROM {FULL_TABLE} WHERE {where} "
        "GROUP BY span_id, span_name ORDER BY min(started_at)",
        parameters=params, query_formats={"FixedString": "string"},
    ).result_rows
    trace = store.get_trace(project, trace_id)
    logical = len(trace.spans) if trace else 0

    print(f"project {project}, trace {trace_id}")
    print(f"  physical rows in {FULL_TABLE}: {physical}")
    for span_id, name, copies in per_span:
        print(f"    {span_id}  {name:<22} {copies} stored cop{'y' if copies == 1 else 'ies'}")
    print(f"  ClickHouseTraceStore.get_trace -> {logical} spans (LIMIT 1 BY span_id, content_hash)")
    if trace:
        for row in trace.spans:
            r = row.record
            extra = f" attempt={r.attempt}" if r.attempt else ""
            extra += f" retry_of={r.retry_of_span_id}" if r.retry_of_span_id else ""
            extra += f" model={r.model} tokens={r.input_tokens}/{r.output_tokens} cost={r.cost}" if r.model else ""
            print(f"    {r.span_id}  {r.span_name:<22} {r.status_code.value:<5} {r.status_description!r}{extra}")
    if physical > logical:
        print(f"  -> dedup: {physical - logical} redelivered row(s) hidden by the read")
    elif physical == logical and logical:
        print("  -> physical = logical: ClickHouse already merged the duplicates in the background")
    print(f"  get_conflicts -> {store.get_conflicts(project, trace_id)}")
    runs = [run for run in store.list_runs(project, 0, 2**63, limit=1000) if run.trace_id == trace_id]
    for run in runs:
        print(f"  list_runs -> root={run.root_name!r} spans={run.span_count} errors={run.error_span_count} "
              f"missing_root={run.missing_root} duration_ms={(run.run_ended_at - run.run_started_at) / 1e6:.0f}")
    ok = trace is not None and logical == len(per_span) and not trace.conflicted and len(runs) == 1
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    command = argv[1]
    if command == "wait-schema":
        return wait_schema(float(argv[2]) if len(argv) > 2 else 60)
    if command == "wait-caught-up":
        return wait_caught_up(float(argv[2]) if len(argv) > 2 else 60)
    if command == "report" and len(argv) == 3:
        return report(argv[2])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
