"""Protocol "1" request body for POST /api/v1/traces, and its mapping to SpanRecord.

Shape follows docs/trace-protocol.md §4 (envelope with `protocol_version` and
`spans`; spans carry `name`, `start_time`, `end_time`, `status`, `attributes`,
`events`, `links`). The optional fields are the SpanRecord columns
(clickhouse-span-record.md §1) under the same names. Times are integer ns.

The client never sends `project_id`, `received_at` or per-span
`protocol_version`: the server sets them, and `extra="forbid"` rejects them.
Payloads are accepted as sent, up to MAX_PAYLOAD_BYTES each: a larger one is
rejected, never truncated here (clickhouse-span-record.md §9 P9). The local-1
payload rejection does not apply.
"""

from __future__ import annotations

import json
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr
from pydantic_core import PydanticCustomError

from agent_debugger_api.contracts import PayloadState, SpanRecord, StatusCode
from agent_debugger_api.contracts.span_record import (
    CostString,
    OperationType,
    SpanId,
    TraceId,
    UInt16,
    UInt32,
    UnixNanos,
)

MAX_SPANS_PER_BATCH = 256
# One payload, in UTF-8 bytes. The same number is the SDK's hard maximum
# (ai_agent_debugger_sdk.capture.MAX_PAYLOAD_BYTES): three payloads at this
# size still fit one Kafka record (clickhouse-span-record.md §9.3).
MAX_PAYLOAD_BYTES = 131_072


def _within_payload_cap(value: str) -> str:
    # UTF-8 is 1 to 4 bytes per character, so most values need no encoding to decide.
    too_long = len(value) > MAX_PAYLOAD_BYTES or (
        len(value) * 4 > MAX_PAYLOAD_BYTES and len(value.encode("utf-8", "surrogatepass")) > MAX_PAYLOAD_BYTES
    )
    if too_long:
        # The message carries the limit only, never the value.
        raise PydanticCustomError("payload_too_large", "Payload exceeds {limit} bytes", {"limit": MAX_PAYLOAD_BYTES})
    return value


Payload = Annotated[StrictStr, AfterValidator(_within_payload_cap)]

Scalar = Union[StrictStr, StrictBool, StrictInt, StrictFloat]
# OTel attribute values: a scalar or a homogeneous-in-practice list of scalars.
AttributeValue = Union[Scalar, list[Scalar]]
Attributes = dict[StrictStr, AttributeValue]


class _Wire(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WireStatus(_Wire):
    code: StatusCode = StatusCode.UNSET
    description: StrictStr = ""


class WireEvent(_Wire):
    name: StrictStr = Field(min_length=1)
    time: UnixNanos
    attributes: Attributes = Field(default_factory=dict)


class WireLink(_Wire):
    trace_id: TraceId
    span_id: SpanId
    relation: StrictStr = Field(min_length=1)


class WireSpan(_Wire):
    trace_id: TraceId
    span_id: SpanId
    parent_span_id: SpanId | None = None
    name: StrictStr = Field(min_length=1)
    operation_type: OperationType
    start_time: UnixNanos
    end_time: UnixNanos
    status: WireStatus = Field(default_factory=WireStatus)

    service_name: StrictStr = ""
    display_label: StrictStr = ""
    execution_mode: StrictStr = ""
    graph_node_id: StrictStr = ""
    graph_node_parent_id: StrictStr = ""
    error_type: StrictStr = ""

    attempt: UInt16 | None = None
    retry_of_span_id: SpanId | None = None

    model: StrictStr | None = None
    provider: StrictStr | None = None
    input_tokens: UInt32 | None = None
    output_tokens: UInt32 | None = None
    total_tokens: UInt32 | None = None
    cost: CostString | None = None

    # A payload the client says nothing about was not produced: "unavailable".
    input_state: PayloadState = PayloadState.UNAVAILABLE
    output_state: PayloadState = PayloadState.UNAVAILABLE
    error_state: PayloadState = PayloadState.UNAVAILABLE
    input_payload: Payload = ""
    output_payload: Payload = ""
    error_payload: Payload = ""

    attributes: Attributes = Field(default_factory=dict)
    events: list[WireEvent] = Field(default_factory=list)
    links: list[WireLink] = Field(default_factory=list)


class TraceBatch(_Wire):
    protocol_version: Literal["1"]
    spans: Annotated[list[WireSpan], Field(min_length=1, max_length=MAX_SPANS_PER_BATCH)]


def stringify(value: AttributeValue) -> str:
    """Attribute value -> the string stored in Map(String, String) (§8.2).

    Strings are kept as they are; everything else is compact JSON, so
    True -> "true", 3 -> "3", 0.2 -> "0.2", ["a", 1] -> '["a",1]'.
    """
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _attributes(attributes: Attributes) -> dict[str, str]:
    return {key: stringify(value) for key, value in attributes.items()}


def to_span_record(span: WireSpan, project_id: UUID, received_at: int) -> SpanRecord:
    """Raises pydantic.ValidationError for cross-field errors (e.g. end before start)."""
    return SpanRecord(
        project_id=project_id,
        trace_id=span.trace_id,
        span_id=span.span_id,
        parent_span_id=span.parent_span_id,
        service_name=span.service_name,
        operation_type=span.operation_type,
        span_name=span.name,
        display_label=span.display_label,
        execution_mode=span.execution_mode,
        graph_node_id=span.graph_node_id,
        graph_node_parent_id=span.graph_node_parent_id,
        status_code=span.status.code,
        status_description=span.status.description,
        error_type=span.error_type,
        started_at=span.start_time,
        ended_at=span.end_time,
        attempt=span.attempt,
        retry_of_span_id=span.retry_of_span_id,
        model=span.model,
        provider=span.provider,
        input_tokens=span.input_tokens,
        output_tokens=span.output_tokens,
        total_tokens=span.total_tokens,
        cost=span.cost,
        input_state=span.input_state,
        output_state=span.output_state,
        error_state=span.error_state,
        input_payload=span.input_payload,
        output_payload=span.output_payload,
        error_payload=span.error_payload,
        attributes=_attributes(span.attributes),
        events=tuple(
            {"name": e.name, "time": e.time, "attributes": _attributes(e.attributes)} for e in span.events
        ),
        links=tuple({"trace_id": link.trace_id, "span_id": link.span_id, "relation": link.relation} for link in span.links),
        protocol_version="1",
        received_at=received_at,
    )
