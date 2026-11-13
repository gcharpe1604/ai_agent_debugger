"""Kafka message value for the durable path (`docs/proposals/clickhouse-span-record.md` §1, §8.2).

One `SpanRecord` = one Kafka message = one ClickHouse row, minus the fields the
trace-writer adds (`content_hash`, `persisted_at`, `kafka_partition`,
`kafka_offset`). `duration_ns` is also left out: §1 says the writer computes it.

Conventions (§5, §8.2):
- every timestamp is integer nanoseconds since the Unix epoch;
- `cost` is a decimal string or None, never a float;
- None means "not recorded" and is never the same as 0 or "".

This is the durable contract (protocol "1"). It is separate from the local-1
ingestion models in `traces/schemas.py`; do not merge them.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

TraceId = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{32}$")]
SpanId = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{16}$")]
# Int64 nanoseconds covers dates up to 2262.
UnixNanos = Annotated[StrictInt, Field(ge=0, le=2**63 - 1)]
UInt16 = Annotated[StrictInt, Field(ge=0, le=2**16 - 1)]
UInt32 = Annotated[StrictInt, Field(ge=0, le=2**32 - 1)]
# Decimal(18, 9): at most 9 integer digits and 9 fractional digits, non-negative.
CostString = Annotated[StrictStr, Field(pattern=r"^[0-9]{1,9}(\.[0-9]{1,9})?$")]

OperationType = Literal["run", "agent", "model", "retrieval", "tool", "api", "state", "custom"]


class StatusCode(str, Enum):
    UNSET = "UNSET"
    OK = "OK"
    ERROR = "ERROR"


class PayloadState(str, Enum):
    """Why a payload is what it is. The UI must never infer this from an empty string."""

    CAPTURED = "captured"  # stored as given
    DISABLED = "disabled"  # capture switched off
    REDACTED = "redacted"  # removed by a secret rule
    TRUNCATED = "truncated"  # cut at the size limit; the stored prefix is real but partial
    UNAVAILABLE = "unavailable"  # not produced or lost


# States whose payload must be empty: nothing was captured.
_EMPTY_PAYLOAD_STATES = frozenset({PayloadState.DISABLED, PayloadState.UNAVAILABLE})


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SpanEvent(_Strict):
    name: StrictStr = Field(min_length=1)
    time: UnixNanos
    attributes: dict[StrictStr, StrictStr] = Field(default_factory=dict)


class SpanLink(_Strict):
    trace_id: TraceId
    span_id: SpanId
    # depends_on, handoff_from, consumes, retry_of, or an OTel link.
    relation: StrictStr = Field(min_length=1)


class SpanRecord(_Strict):
    # Identity. project_id is set server-side (resolve_project_id), never from the client.
    project_id: UUID
    trace_id: TraceId
    span_id: SpanId
    parent_span_id: SpanId | None  # None = root. A missing parent is kept, not rejected.

    # What ran.
    service_name: StrictStr
    operation_type: OperationType
    span_name: StrictStr = Field(min_length=1)
    display_label: StrictStr = ""
    execution_mode: StrictStr = ""  # today "live" / "controlled"; not enforced
    graph_node_id: StrictStr = ""  # workflow-graph node; never used for the span tree
    graph_node_parent_id: StrictStr = ""

    # How it ended.
    status_code: StatusCode
    status_description: StrictStr = ""
    error_type: StrictStr = ""

    # When.
    started_at: UnixNanos
    ended_at: UnixNanos

    # Retries.
    attempt: UInt16 | None = None
    retry_of_span_id: SpanId | None = None

    # Model usage. None = not recorded.
    model: StrictStr | None = None
    provider: StrictStr | None = None
    input_tokens: UInt32 | None = None
    output_tokens: UInt32 | None = None
    total_tokens: UInt32 | None = None
    cost: CostString | None = None  # only when the span supplies it; never computed

    # Payloads. Each carries its own state; the state has no default on purpose.
    input_state: PayloadState
    output_state: PayloadState
    error_state: PayloadState
    input_payload: StrictStr = ""
    output_payload: StrictStr = ""
    error_payload: StrictStr = ""

    # Flexible data.
    attributes: dict[StrictStr, StrictStr] = Field(default_factory=dict)
    events: tuple[SpanEvent, ...] = ()
    links: tuple[SpanLink, ...] = ()

    # Receipt metadata. received_at is set once per envelope by FastAPI.
    protocol_version: Literal["1"]
    received_at: UnixNanos

    @model_validator(mode="after")
    def _check(self) -> SpanRecord:
        if self.ended_at < self.started_at:
            raise ValueError("ended_at is before started_at")
        for kind in ("input", "output", "error"):
            state = getattr(self, f"{kind}_state")
            if state in _EMPTY_PAYLOAD_STATES and getattr(self, f"{kind}_payload"):
                raise ValueError(f"{kind}_payload must be empty when {kind}_state is {state.value}")
        return self

    @property
    def duration_ns(self) -> int:
        """Convenience only; not part of the message. The writer stores its own copy."""
        return self.ended_at - self.started_at

    @property
    def kafka_key(self) -> bytes:
        """Message key (§8.2): all spans of a trace land on one partition."""
        return self.trace_id.encode("ascii")
