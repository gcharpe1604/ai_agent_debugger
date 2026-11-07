"""Bounded ended-span view for the explicit localhost ingestion profile."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator

TraceId = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
SpanId = Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")]
Nano = Annotated[str, Field(pattern=r"^[0-9]{1,19}$")]
Scalar = StrictStr | StrictInt | StrictFloat | StrictBool


class Attributes(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Event(Attributes):
    name: str = Field(min_length=1, max_length=128)
    time_unix_nano: Nano
    attributes: dict[str, Scalar] = Field(default_factory=dict, max_length=8)


class Status(Attributes):
    code: Literal["OK", "ERROR", "UNSET"]


class SpanRecord(Attributes):
    trace_id: TraceId
    span_id: SpanId
    parent_span_id: SpanId | None
    name: str = Field(min_length=1, max_length=256)
    operation_type: Literal["run", "agent", "model", "tool", "retrieval", "api", "state", "custom"]
    start_time_unix_nano: Nano
    end_time_unix_nano: Nano
    status: Status
    attributes: dict[str, Scalar] = Field(default_factory=dict, max_length=32)
    resource: dict[str, str] = Field(default_factory=dict, max_length=4)
    events: list[Event] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def bounded_metadata(self):
        if not int(self.trace_id, 16) or not int(self.span_id, 16):
            raise ValueError("Nonzero OpenTelemetry IDs required")
        if self.parent_span_id is not None and (not int(self.parent_span_id, 16) or self.parent_span_id == self.span_id):
            raise ValueError("Invalid recorded parent")
        if int(self.end_time_unix_nano) < int(self.start_time_unix_nano):
            raise ValueError("Ended span has reversed timestamps")
        for values in [self.attributes, self.resource, *(event.attributes for event in self.events)]:
            if any(len(key) > 128 or (isinstance(value, str) and len(value) > 1024) for key, value in values.items()):
                raise ValueError("Metadata limit exceeded")
            if any(key.startswith(("debugger.input", "debugger.output")) for key in values):
                raise ValueError("Payload capture is disabled for this local ingestion profile")
        return self


class Batch(Attributes):
    protocol_version: Literal["local-1"]
    spans: list[SpanRecord] = Field(min_length=1, max_length=64)
