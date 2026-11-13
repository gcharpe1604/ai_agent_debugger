"""Builders for valid SpanRecord values in tests."""

from uuid import UUID

from agent_debugger_api.contracts import SpanRecord

PROJECT_A = UUID("00000000-0000-4000-8000-00000000000a")
PROJECT_B = UUID("00000000-0000-4000-8000-00000000000b")
TRACE_1 = "1" * 32
TRACE_2 = "2" * 32
T0 = 1_763_000_000_000_000_000  # ns


def span_fields(**overrides) -> dict:
    fields = {
        "project_id": PROJECT_A,
        "trace_id": TRACE_1,
        "span_id": "a" * 16,
        "parent_span_id": None,
        "service_name": "rag_agent",
        "operation_type": "run",
        "span_name": "rag.run",
        "status_code": "OK",
        "started_at": T0,
        "ended_at": T0 + 1_000,
        "input_state": "captured",
        "output_state": "captured",
        "error_state": "unavailable",
        "protocol_version": "1",
        "received_at": T0 + 5_000,
    }
    fields.update(overrides)
    return fields


def make_span(**overrides) -> SpanRecord:
    return SpanRecord.model_validate(span_fields(**overrides))
