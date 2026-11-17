"""Hand-built traces for investigator tests. No Kafka, ClickHouse or network.

Spans go through `InMemoryTraceStore` with the writer's real `content_hash`,
so a `TraceRead` here has the same shape as one read from ClickHouse.
"""

import json

from agent_debugger_api.contracts import SpanRecord, TraceRead
from agent_debugger_api.contracts.fakes import InMemoryTraceStore
from agent_debugger_api.investigator.schema import InvestigatorOutput
from agent_debugger_api.investigator.snapshot import Snapshot, SnapshotLimits, build_snapshot
from agent_debugger_api.trace_writer.content_hash import content_hash
from tests.contracts.factories import PROJECT_A, T0, TRACE_1, make_span

MS = 1_000_000

# Span numbers used by the named traces below.
ROOT, AGENT, PLAN, ORDER, RESERVE = 1, 2, 3, 4, 5
PAY_1, PAY_2, PAY_3 = 6, 7, 8

PLAN_OUTPUT = '{"plan":[{"step_id":"reserve","arguments":{"quantity":0}}]}'
ORDER_OUTPUT = '{"result":{"order_id":"ORD-100","quantity":2}}'
RESERVE_INPUT = '{"tool":"reserve_inventory","arguments":{"quantity":0}}'


def sid(number: int) -> str:
    return f"{number:016x}"


def span(number: int, parent: int | None = None, *, start: int = 0, duration: int = 1, **overrides) -> SpanRecord:
    """An OK tool span with no payloads; `start` and `duration` are milliseconds from T0."""
    fields = {
        "span_id": sid(number),
        "parent_span_id": None if parent is None else sid(parent),
        "operation_type": "tool",
        "span_name": f"span-{number}",
        "started_at": T0 + start * MS,
        "ended_at": T0 + (start + duration) * MS,
        "input_state": "unavailable",
        "output_state": "unavailable",
        "error_state": "unavailable",
    }
    fields.update(overrides)
    return make_span(**fields)


def error_span(number: int, parent: int | None = None, *, error_type: str = "ToolError", **overrides) -> SpanRecord:
    """An ERROR span as the SDK exports one: error type, exception event, error payload."""
    start = overrides.get("start", 0)
    fields = {
        "status_code": "ERROR",
        "error_type": error_type,
        "error_state": "captured",
        "error_payload": json.dumps({"type": error_type, "message": f"{error_type} during span-{number}"}),
        "events": [
            {
                "name": "exception",
                "time": T0 + start * MS,
                "attributes": {"exception.type": error_type, "exception.message": f"{error_type} during span-{number}"},
            }
        ],
    }
    fields.update(overrides)
    return span(number, parent, **fields)


def captured(**payloads: str) -> dict:
    """`captured(input="...", output="...")` -> state and payload fields."""
    fields = {}
    for kind, text in payloads.items():
        fields[f"{kind}_state"] = "captured"
        fields[f"{kind}_payload"] = text
    return fields


def read(*records: SpanRecord) -> TraceRead:
    store = InMemoryTraceStore(content_hash)
    store.insert_spans(records)
    return store.get_trace(PROJECT_A, TRACE_1)


def snapshot_of(*records: SpanRecord, limits: SnapshotLimits = SnapshotLimits()) -> Snapshot:
    return build_snapshot(read(*records), PROJECT_A, TRACE_1, limits)


def failed_tool_trace(payloads: bool = True) -> list[SpanRecord]:
    """TOOL-03's shape: the plan asks for quantity 0, the reserve call fails, the run fails.

    root (ERROR) > agent > plan (OK), order (OK), reserve (ERROR).
    """
    plan = captured(output=PLAN_OUTPUT) if payloads else {}
    order = captured(output=ORDER_OUTPUT) if payloads else {}
    reserve = captured(input=RESERVE_INPUT) if payloads else {}
    return [
        span(ROOT, start=0, duration=50, operation_type="run", status_code="ERROR", execution_mode="controlled",
             attributes={"debugger.result.status": "failed"}),
        span(AGENT, ROOT, start=1, duration=40, operation_type="agent"),
        span(PLAN, AGENT, start=2, operation_type="custom", span_name="controlled.plan", **plan),
        span(ORDER, AGENT, start=4, attempt=1, attributes={"debugger.step": "order", "debugger.attempt": "1"}, **order),
        error_span(RESERVE, AGENT, start=6, attempt=1,
                   attributes={"debugger.step": "reserve", "debugger.attempt": "1"}, **reserve),
    ]


def retry_trace(*statuses: str) -> list[SpanRecord]:
    """`pay` attempts chained by retry_of, one per status: retry_trace("ERROR", "OK") is TOOL-07's shape."""
    records = [
        span(ROOT, start=0, duration=50, operation_type="run", execution_mode="controlled",
             status_code="ERROR" if statuses[-1] == "ERROR" else "OK"),
        span(AGENT, ROOT, start=1, duration=40, operation_type="agent"),
    ]
    for index, status in enumerate(statuses):
        number = PAY_1 + index
        fields = {
            "start": 10 + index * 2,
            "attempt": index + 1,
            "retry_of_span_id": sid(number - 1) if index else None,
            "attributes": {"debugger.step": "pay", "debugger.attempt": str(index + 1)},
        }
        make = error_span if status == "ERROR" else span
        records.append(make(number, AGENT, **fields))
    return records


def evidence(number: int, field: str = "status_code", **more) -> dict:
    return {"span_id": sid(number), "field": field, **more}


def finding(**overrides) -> dict:
    """A candidate that grounds on `failed_tool_trace()`: an observed failure on the reserve span."""
    candidate = {
        "category": "tool_failure",
        "claim_type": "observed_failure",
        "suspicious_span_id": sid(RESERVE),
        "priority": "HIGH",
        "explanation": "The reserve call recorded an error.",
        "evidence": [evidence(RESERVE)],
    }
    candidate.update(overrides)
    return candidate


def output(*findings: dict, verdict: str | None = None, limitations=()) -> InvestigatorOutput:
    return InvestigatorOutput.model_validate(output_dict(*findings, verdict=verdict, limitations=limitations))


def output_dict(*findings: dict, verdict: str | None = None, limitations=()) -> dict:
    return {
        "schema_version": 1,
        "verdict": verdict or ("findings" if findings else "no_issue_found"),
        "findings": list(findings),
        "limitations": list(limitations),
    }
